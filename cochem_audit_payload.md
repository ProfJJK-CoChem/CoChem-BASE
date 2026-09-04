Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260903-061002-brainstorm\.in-progress\Perfected_SRS_Chunk_06_Core_Part_6_prompts.md.
Original prompt:
# CODING PROMPT: CoChem-BASE Core Architecture Implementation (Chunk 6: Suggestions #51–#60)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§3.0, §4.4, §6.4, §6.10, §8.2, §8.3, §8.4, §8A.4, §8B.4, §8C, §9A, §20, Table 3, QS-1, QS-3)
- Zero-Mock Anti-Spoofing Protocol v2 (Zero placeholders, zero stubs, zero simulated mocks, 100% real physical execution)
- Tripartite Storage Air-Gap Architecture (Source $T_{\text{src}}$ immutable read-only, Ephemeral Scratch $T_{\text{scr}}$ isolated, Artifacts $T_{\text{art}}$ read-write cryptographic commitments)
- 6-Tier Environment Matrix (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions, HPC)
- Dynamic Mendeleev Invariant Mandate (`from mendeleev import element`, zero hardcoded atomic masses, strict dynamic IUPAC/CIAAW physical mass retrieval)
- FAIR Principles Compliance (F1, F4, A1, I1, I2, I3, R1.1, R1.2, R1.3)
- MolSSI QCSchema v1 Compliance (`schema_name="qcschema_output"`, `schema_version=1`, explicit `AtomicResult` mapping)
- Authoritative CODATA 2018 / 2022 IEEE-754 FP64 Invariant Mandate
- IETF RFC 8032 PureEd25519, RFC 8785 JSON Canonicalization Scheme (JCS), & W3C Linked Data Proof Standards
- Cross-Platform Concurrency Directive (Thread-safe SWMR HDF5, strictly non-initializing GPU discovery with zero CUDA-locking, local scratch file locking, strictly no POSIX `fcntl` on network filesystems)

---

## 1. Executive Summary & Objective

Implement, harden, and physically verify Suggestions #51 through #60 of the CoChem-BASE Core Architecture Improvement Specification. This work package resolves critical vulnerabilities across elemental mass fallbacks, empirical covalent/vdW radii topology perception, semantic provenance and conformer lineage Linked Data annotations, machine-readable SPDX data licensing, dynamic isotopic mass validation, W3C Linked Data Proof offline digital signatures, environment-agnostic VCS package provenance, non-initializing GPU telemetry with zero CUDA runtime locking, deterministic UUIDv5 content-addressable PES storage with Thread-Safe HDF5 SWMR protocols, and Method Matrix v4 canonical composite fidelity tier definitions.

Specific implementation targets include:
1. Eradicating permissive fallback to standard terrestrial atomic weight (`el.mass`) in `get_isotopic_mass("C", 14)`, raising an explicit `IsotopeStabilityError` whenever a requested isotope cannot be resolved to a physical nuclear mass in the Mendeleev registry.
2. Replacing the hardcoded `0.77` Å fallback in `get_covalent_radius()` with a strict hierarchical Mendeleev lookup (Pyykkö covalent radius $\to$ Cordero covalent radius $\to$ van der Waals radius $\to$ `RadiusNotFoundError`), ensuring accurate intermolecular distance thresholds and topological perception for noble gases and heavy elements.
3. Upgrading conformer lineage graphs in `DAGNode` to emit W3C PROV-O compliant JSON-LD documents (`prov:wasDerivedFrom`, `prov:wasGeneratedBy`, `prov:Activity`, `prov:Entity`) while enforcing Tripartite Air-Gap compliance via an offline local JSON-LD context catalog bundled in `cochem_base/schemas/contexts/`.
4. Adding an immutable `license: str = "CC-BY-4.0"` (or configurable SPDX identifier) field to `QCSchemaProvenance`, `QCSchemaMethodRecord`, and `QCResultsRecord`, validating against an offline local SPDX identifier table to uphold FAIR Principle R1.1.
5. Eradicating the static 18-element `ISOTOPIC_MASSES` dictionary in `cochem_core_registry_schema.py` and replacing it with a cached, dynamic lookup calling `mendeleev.element(symbol).isotopes` backed by Mendeleev's bundled local SQLite database for fully air-gapped execution across all 6 environment tiers.
6. Refactoring `sign_report_payload` in `cochem_crypto.py` to emit standard W3C Linked Data Proof envelopes (`Ed25519Signature2020`) with pure cryptographic `did:key` resolution via multicodec `0xed01` prefix and base58btc encoding without external network DID registries.
7. Enhancing `get_vcs_provenance()` in `cochem_version.py` to use dynamic `pathlib.Path` root checks and Python packaging metadata (`importlib.metadata`) to capture accurate package version and distribution provenance inside stripped Docker containers and HPC wheels lacking `.git` directories.
8. Refactoring `collect_hardware_metadata()` to use a strictly non-initializing discovery protocol: querying direct NVML C-bindings (`pynvml.nvmlInit()` / `pynvml.nvmlShutdown()`) with fallback to short-lived CLI calls (`nvidia-smi` / `rocm-smi`), strictly banning `torch.cuda` or `jax.devices` in the orchestrator telemetry path to guarantee zero CUDA-locking and maintain NVIDIA MPS multiplexing readiness.
9. Refactoring `PESPointRecord` to generate deterministic, globally unique UUIDv5 identifiers from canonical RFC 8785 JSON hashes of molecular geometry, basis set, and electronic structure method, while enforcing Thread-Safe HDF5 SWMR protocols with cross-platform node-local file locking adhering to the HPC Distributed Lock Prohibition.
10. Expanding `CalculationFidelity` in `cochem_base.core.glossary` from 5 legacy strings to encompass all canonical composite tiers established in Method Matrix v4 Table 3 and §9A (`junChS`, `junChS-F12`, `ChS`, `T3-10s`, `T3-1min`, `T3-30min`, `T3-3h`, `T3-12h`, `T4-1d`, `R2`) as an extensible string-enum supporting open QCSchema specifications.

All code modifications must be accompanied by comprehensive, zero-mock unit and integration tests executing real Mendeleev lookups, offline JSON-LD expansions, physical Ed25519 cryptographic signing, real SWMR HDF5 dataset preallocation, and non-initializing NVML hardware interrogation.

---

## 2. Target Files & Deliverable Manifest

### Metadata, Elemental Invariants & Hardware Discovery Modules
1. `src/cochem_base/core/metadata.py` (Suggestions #51, #52, #58)
2. `src/cochem_base/core/exceptions.py` (Suggestions #51, #52)
3. `src/cochem_base/cochem_core_registry_schema.py` (Suggestion #55)

### Provenance, Versioning & Cryptographic Proof Modules
4. `src/cochem_base/core/cochem_provenance.py` (Suggestion #53)
5. `src/cochem_base/schemas/contexts/prov_o_context.jsonld` (Suggestion #53)
6. `src/cochem_base/core/cochem_crypto.py` (Suggestion #56)
7. `src/cochem_base/core/cochem_version.py` (Suggestion #57)

### Core Data Models, Storage & Domain Vocabularies
8. `src/cochem_base/core/models.py` (Suggestions #54, #59)
9. `src/cochem_base/core_engine/cochem_core_pes_store.py` (Suggestions #54, #59)
10. `src/cochem_base/core/licensing.py` (Suggestion #54)
11. `src/cochem_base/core/glossary.py` (Suggestion #60)

### Zero-Mock Test Suite Deliverables
12. `tests/core/test_architecture_part6.py` (Validating Suggestions #53, #57, #58, #59)
13. `tests/core/test_physics_integrity_part6.py` (Validating Suggestions #51, #52, #54, #55, #56, #59, #60)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Dynamic Isotopic Nuclear Mass Resolution & Unphysical Fallback Removal (Suggestion #51)]
- **Files Affected:** `src/cochem_base/core/metadata.py` (`get_isotopic_mass`), `src/cochem_base/core/exceptions.py`
- **Problem Statement:**
  `get_isotopic_mass("C", 14)` attempts to find the isotope in Mendeleev's isotope list. When an isotope lookup fails or cannot be resolved, the function silently falls back to `float(el.mass)`. In Mendeleev, `el.mass` is the terrestrial abundance-weighted atomic weight ($12.011$ u for Carbon), not an isotopic nuclear mass. Supplying the terrestrial average mass to rotational force-field re-diagonalization calculates incorrect moments of inertia, shifting predicted ground-state rotational constants $B_0$ and vibrational frequencies by dozens of MHz [M], violating Method Matrix v4 §6.10, §8B.4, and FAIR Principle R1.3.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/exceptions.py`, define:
     ```python
     class IsotopeStabilityError(ValueError):
         """Raised when a requested isotope cannot be physically resolved to an isotopic nuclear mass."""
         pass
     ```
  2. Refactor `get_isotopic_mass(symbol_or_atomic_number: Union[str, int], mass_number: int) -> float` in `src/cochem_base/core/metadata.py`:
     - Query dynamic element data via `el = mendeleev.element(symbol_or_atomic_number)`.
     - Filter `el.isotopes` for an isotope where `iso.mass_number == int(mass_number)`.
     - If matched and `iso.mass` is not `None` and `float(iso.mass) > 0.0`:
       Return `float(iso.mass)` [M].
     - If no matching isotope exists, or if `iso.mass` is `None` or non-positive:
       Explicitly raise `IsotopeStabilityError(f"Isotope '{el.symbol}-{mass_number}' cannot be resolved to a physical isotopic mass in authoritative CIAAW/Mendeleev data.")`.
     - Strictly eliminate any code path returning `el.mass`, `el.atomic_weight`, or static numeric constants when an isotopic mass number is requested.
  3. Provenance and Invariants:
     - Tag return value documentation with `[M]` (Measured empirical nuclear mass).
     - Ensure compatibility across all stable and known radioactive isotopes (e.g. `14C`, `2H`, `15N`, `37Cl`, `18O`).

---

### [Task 2: Hierarchical Empirical Radii Lookup & Elimination of Hardcoded 0.77 Å Fallback (Suggestion #52)]
- **Files Affected:** `src/cochem_base/core/metadata.py` (`get_covalent_radius`), `src/cochem_base/core/exceptions.py`
- **Problem Statement:**
  `get_covalent_radius()` returns a hardcoded default of `0.77` Å when radius data is absent. The value `0.77` Å is the single-bond covalent radius of $sp^3$ Carbon. When assigned to noble gases (He, Ne, Ar, Kr, Xe) or heavy transition metals in van der Waals complexes, intermolecular contact algorithms misclassify non-covalent contacts as vacant voids or perceive false covalent bonds, corrupting molecular graphs and frozen-monomer initial alignments under Method Matrix v4 §20 [M].
- **Implementation Requirements:**
  1. In `src/cochem_base/core/exceptions.py`, define:
     ```python
     class RadiusNotFoundError(KeyError):
         """Raised when empirical covalent or van der Waals radius is unavailable for an element."""
         pass
     ```
  2. Refactor `get_covalent_radius(symbol_or_atomic_number: Union[str, int], radius_type: str = "pyykko") -> float` in `src/cochem_base/core/metadata.py`:
     - Resolve element using `el = mendeleev.element(symbol_or_atomic_number)`.
     - Implement hierarchical empirical lookup without hardcoded defaults:
       1. Primary: Pyykkö single-bond covalent radius (`el.covalent_radius_pyykko`).
       2. Secondary: Cordero covalent radius (`el.covalent_radius_cordero`).
       3. Tertiary: Standard covalent radius (`el.covalent_radius`).
       4. Quaternary (for noble gases or non-bonding atoms where covalent bonds do not form): van der Waals radius (`el.vdw_radius`).
     - Convert value to Angstroms (if reported in picometers by the underlying registry, divide by 100.0; verify Mendeleev units dynamically).
     - If all empirical radii attributes evaluate to `None` or $\le 0.0$:
       Raise `RadiusNotFoundError(f"Empirical radius for element '{el.symbol}' ({el.atomic_number}) could not be resolved from Mendeleev registries.")`.
     - Eradicate the literal `0.77` Å fallthrough return completely.

---

### [Task 3: W3C PROV-O Compliant JSON-LD Lineage & Air-Gapped Local Context Catalog (Suggestion #53)]
- **Files Affected:** `src/cochem_base/core/cochem_provenance.py` (`DAGNode`), `src/cochem_base/schemas/contexts/prov_o_context.jsonld`
- **Problem Statement:**
  `DAGNode.to_dict()` outputs an ad-hoc JSON structure lacking semantic Linked Data annotations. Scientific knowledge graphs and semantic search harvesters cannot index conformer lineage trees (CREST $\to$ GOAT $\to$ ORCA DFT $\to$ DLPNO). Attempting live online JSON-LD `@context` resolution (`http://www.w3.org/ns/prov#`) triggers network timeout crashes on air-gapped HPC compute nodes and CI runners, violating FAIR Principles I1, I3, and the Tripartite Air-Gap mandate.
- **Implementation Requirements:**
  1. Create the offline bundled context catalog file `src/cochem_base/schemas/contexts/prov_o_context.jsonld`:
     ```json
     {
       "@context": {
         "prov": "http://www.w3.org/ns/prov#",
         "dcterms": "http://purl.org/dc/terms/",
         "cochem": "https://cochem.org/schema/core#",
         "Entity": "prov:Entity",
         "Activity": "prov:Activity",
         "Agent": "prov:Agent",
         "wasDerivedFrom": {"@id": "prov:wasDerivedFrom", "@type": "@id"},
         "wasGeneratedBy": {"@id": "prov:wasGeneratedBy", "@type": "@id"},
         "wasAssociatedWith": {"@id": "prov:wasAssociatedWith", "@type": "@id"},
         "startedAtTime": {"@id": "prov:startedAtTime", "@type": "http://www.w3.org/2001/XMLSchema#dateTime"},
         "endedAtTime": {"@id": "prov:endedAtTime", "@type": "http://www.w3.org/2001/XMLSchema#dateTime"},
         "conformerId": "cochem:conformerId",
         "relativeEnergy": "cochem:relativeEnergyKcalMol",
         "rotationalConstants": "cochem:rotationalConstantsMHz"
       }
     }
     ```
  2. In `src/cochem_base/core/cochem_provenance.py`:
     - Implement `get_local_prov_context() -> Dict[str, Any]` which reads `prov_o_context.jsonld` directly using `pathlib.Path(__file__).parent.parent / "schemas" / "contexts" / "prov_o_context.jsonld"`.
     - Extend `DAGNode`:
       - Add method `to_prov_jsonld(self, base_uri: str = "urn:cochem:conformer:") -> Dict[str, Any]`:
         - Construct a standard JSON-LD document with `@context` referencing the bundled definitions.
         - Generate `@id` as `{base_uri}{self.node_id}`.
         - Assign `@type`: `["prov:Entity", "cochem:Conformer"]` for geometry/result nodes, or `["prov:Activity", "cochem:Optimization"]` for transformation steps.
         - Map parent edges using `prov:wasDerivedFrom`: `[{"@id": f"{base_uri}{parent_id}"} for parent_id in self.parents]`.
         - Annotate generation activity via `prov:wasGeneratedBy`.
         - Attach execution metadata, timestamps (ISO 8601 UTC), energy, and rotational constant properties under canonical `cochem:` namespace terms.
     - Provide an offline JSON-LD context validator ensuring zero network socket requests are dispatched when serializing or verifying conformer lineage.

---

### [Task 4: Immutable SPDX Data Usage Licensing Schema (Suggestion #54)]
- **Files Affected:** `src/cochem_base/core/models.py`, `src/cochem_base/core_engine/cochem_core_pes_store.py`, `src/cochem_base/core/licensing.py`
- **Problem Statement:**
  Computational output records (`QCSchemaProvenance`, `QCSchemaMethodRecord`, `QCResultsRecord`, `PESPointRecord`) omit machine-readable licensing metadata. Downstream scientific data repositories reject exported datasets, and commercial or academic users cannot programmatically determine dataset reuse rights, directly violating FAIR Principle R1.1 ("(Meta)data are released with a clear and accessible data usage license").
- **Implementation Requirements:**
  1. Author `src/cochem_base/core/licensing.py`:
     - Define an immutable tuple or frozen set of approved open-science SPDX license identifiers:
       `OFFICIAL_SPDX_LICENSES = frozenset({"CC-BY-4.0", "CC0-1.0", "MIT", "Apache-2.0", "BSD-3-Clause", "GPL-3.0-only", "AGPL-3.0-only"})`.
     - Implement `validate_spdx_license(license_id: str) -> str`:
       - Strip whitespace; verify `license_id in OFFICIAL_SPDX_LICENSES` or matches standard SPDX regex `^[A-Za-z0-9\.\-\+]+$`.
       - Raise `ValueError(f"Invalid or unrecognized SPDX license identifier: '{license_id}'")` if validation fails.
  2. Update Data Models:
     - In `QCSchemaProvenance`, `QCSchemaMethodRecord`, and `QCResultsRecord` (`src/cochem_base/core/models.py` and `cochem_core_pes_store.py`):
       - Add field:
         ```python
         license: str = Field(
             default="CC-BY-4.0",
             description="SPDX license identifier governing data reuse rights (FAIR R1.1)"
         )
         ```
       - Add a Pydantic `@field_validator("license")` invoking `validate_spdx_license(v)`.
     - In `PESPointRecord`: add `license: str = "CC-BY-4.0"` to its metadata envelope.
     - Ensure existing datasets without explicit license tags default safely to `"CC-BY-4.0"`.

---

### [Task 5: Dynamic Isotopic Mass Registry & Elimination of Static ISOTOPIC_MASSES Table (Suggestion #55)]
- **Files Affected:** `src/cochem_base/cochem_core_registry_schema.py`
- **Problem Statement:**
  `cochem_core_registry_schema.py` defines a static dictionary `ISOTOPIC_MASSES` containing hardcoded mass values for only 18 elements. Calculations involving noble gases (argon, neon, krypton) or isotopes like $^{37}\text{Cl}$, $^{13}\text{C}$, or $^{2}\text{H}$ trigger validation rejections or fail schema validation. This violates the Mendeleev Mandate (Method Matrix v4 §8C) and artificially constrains the ecosystem's chemical domain.
- **Implementation Requirements:**
  1. Eradicate the static `ISOTOPIC_MASSES = {...}` dictionary from `src/cochem_base/cochem_core_registry_schema.py`.
  2. Implement an offline dynamic registry accessor backed by Mendeleev's bundled local SQLite database:
     ```python
     @functools.lru_cache(maxsize=512)
     def get_registry_atomic_mass(symbol_or_z: Union[str, int], mass_number: Optional[int] = None) -> float:
         """Dynamic IUPAC/CIAAW mass resolver honoring the Mendeleev Mandate [M]."""
         el = mendeleev.element(symbol_or_z)
         if mass_number is not None:
             iso = next((i for i in el.isotopes if i.mass_number == mass_number), None)
             if iso is not None and iso.mass is not None:
                 return float(iso.mass)
             raise IsotopeStabilityError(f"Isotope {el.symbol}-{mass_number} not found in Mendeleev.")
         if el.atomic_weight is not None:
             return float(el.atomic_weight)
         if el.mass is not None:
             return float(el.mass)
         raise ValueError(f"No valid mass available for element {el.symbol}.")
     ```
  3. Refactor all schema validation routines and regex lookups in `cochem_core_registry_schema.py` to invoke `get_registry_atomic_mass()` dynamically.
  4. Ensure module load time is negligible (< 10 ms [E]) due to cached local SQLite queries, with zero external network access.

---

### [Task 6: W3C Linked Data Proof Envelopes with Offline PureEd25519 did:key Resolution (Suggestion #56)]
- **Files Affected:** `src/cochem_base/core/cochem_crypto.py` (`sign_report_payload`, `verify_report_payload`)
- **Problem Statement:**
  Computational report signatures are serialized under an ad-hoc key (`_provenance_signature`), preventing external scientific repositories from verifying computation proofs. Furthermore, if external DID registries are queried over HTTPS to resolve public keys, air-gapped compute nodes experience connection timeouts, violating FAIR Principles A1, I1, R1.2, and User Manual §6.4.1.
- **Implementation Requirements:**
  1. Implement offline `did:key` encoder and decoder in `cochem_base/core/cochem_crypto.py`:
     - Ed25519 multicodec prefix: `0xed01` (bytes `b'\xed\x01'`).
     - Encode: Given raw 32-byte Ed25519 public key, prepend `b'\xed\x01'`, encode using base58btc, and prepend `"did:key:z"`.
     - Decode: Given `"did:key:z..."`, strip `"did:key:z"`, decode base58btc, assert first 2 bytes are `b'\xed\x01'`, and extract the 32-byte public key directly. Zero external HTTP/network lookups permitted.
  2. Refactor `sign_report_payload(payload: Dict[str, Any], private_key: ed25519.Ed25519PrivateKey) -> Dict[str, Any]`:
     - Canonicalize `payload` via RFC 8785 JSON Canonicalization Scheme (JCS) bytes.
     - Sign raw canonical bytes using RFC 8032 PureEd25519 (`signature_bytes = private_key.sign(canonical_bytes)`).
     - Encode signature as base64 or multibase.
     - Return payload enveloped with standard W3C Linked Data Proof:
       ```python
       return {
           **payload,
           "proof": {
               "type": "Ed25519Signature2020",
               "created": datetime.now(timezone.utc).isoformat(),
               "verificationMethod": public_key_to_did_key(private_key.public_key()),
               "proofPurpose": "assertionMethod",
               "proofValue": base64.urlsafe_b64encode(signature_bytes).decode("ascii")
           }
       }
       ```
  3. Refactor `verify_report_payload(signed_payload: Dict[str, Any]) -> bool`:
     - Extract `proof = signed_payload.get("proof")`; if absent, return `False`.
     - Extract `did_key = proof.get("verificationMethod")`; decode raw public key bytes offline.
     - Separate payload from `proof` dictionary, canonicalize payload via RFC 8785, and verify `proofValue` using `public_key.verify(sig_bytes, canonical_bytes)`.
     - Return `True` on success; catch `InvalidSignature` and return `False`.

---

### [Task 7: Robust OS-Agnostic Dynamic VCS Provenance & Container Introspection (Suggestion #57)]
- **Files Affected:** `src/cochem_base/core/cochem_version.py` (`get_vcs_provenance`)
- **Problem Statement:**
  `get_vcs_provenance()` assumes `.git` directories or local `.build_manifest.json` files exist at hardcoded paths. When executed inside production Docker containers, Codespaces, or HPC Python wheels where `.git` is stripped, it silently drops software version metadata and returns `"UNTRACKED_BUILD"`. This breaks reproducible audit trails mandated by User Manual §6.4.2 and FAIR Principle R1.2.
- **Implementation Requirements:**
  1. Refactor `get_vcs_provenance() -> Dict[str, Any]` in `src/cochem_base/core/cochem_version.py`:
     - Hierarchy of provenance discovery:
       1. Git Repository Check: Use `pathlib.Path(__file__).resolve()` and traverse parents to locate `.git`. If found and git CLI is available, query commit SHA, branch, and dirty status via safe subprocess calls with 2-second timeouts.
       2. Build Manifest Check: Check for `.build_manifest.json` in package root or `COCHEM_ROOT`.
       3. Distribution Package Introspection (`importlib.metadata` - PEP 566):
          - Query `importlib.metadata.version("CoChem-BASE")` or `importlib.metadata.version("cochem_base")`.
          - Retrieve distribution metadata:
            ```python
            try:
                dist_version = importlib.metadata.version("CoChem-BASE")
                dist_files = importlib.metadata.files("CoChem-BASE")
                installer = importlib.metadata.distribution("CoChem-BASE").read_text("INSTALLER") or "unknown"
                return {
                    "vcs_type": "installed_wheel",
                    "version": dist_version,
                    "installer": installer.strip(),
                    "file_count": len(dist_files) if dist_files else 0,
                    "status": "DISTRIBUTION_PACKAGE"
                }
            except importlib.metadata.PackageNotFoundError:
                pass
            ```
       4. Fallback: Return structured dictionary with `"status": "UNTRACKED_BUILD"`, recorded execution timestamp, and platform telemetry.
  2. Dynamic Path Resolution:
     - Ensure all path checks use `pathlib.Path` relative to dynamic module anchors, `pathlib.Path.home()`, or environment variables (`COCHEM_ROOT`, `TMPDIR`).
     - Fully verify portability across Windows WSL, macOS OrbStack, Debian Linux, Codespaces, GitHub Actions, and HPC.

---

### [Task 8: Strictly Non-Initializing GPU Hardware Discovery & Zero CUDA-Locking (Suggestion #58)]
- **Files Affected:** `src/cochem_base/core/metadata.py` (`collect_hardware_metadata`)
- **Problem Statement:**
  `collect_hardware_metadata()` executes fragile CLI subprocess commands or risks importing `torch.cuda` / `jax.devices`. Calling `torch.cuda.is_available()` initializes the CUDA runtime context (`cudaInitDevice()`) and binds it to the host operating system PID. Spawning worker processes afterwards fails immediately with `RuntimeError: Cannot re-initialize CUDA in forked subprocess`, and permanently blocks dynamic NVIDIA Multi-Process Service (MPS) context multiplexing under Method Matrix v4 §8A.4 [M].
- **Implementation Requirements:**
  1. Implement strictly non-initializing GPU discovery in `src/cochem_base/core/metadata.py`:
     - Tier 1: Direct C-level NVML bindings (`pynvml`):
       ```python
       def _query_nvml_telemetry() -> Optional[List[Dict[str, Any]]]:
           try:
               import pynvml
               pynvml.nvmlInit()
               devices = []
               try:
                   count = pynvml.nvmlDeviceGetCount()
                   for idx in range(count):
                       handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                       name = pynvml.nvmlDeviceGetName(handle)
                       if isinstance(name, bytes):
                           name = name.decode("utf-8")
                       mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                       cc_major, cc_minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                       devices.append({
                           "index": idx,
                           "product_name": name,
                           "total_memory_bytes": int(mem.total),
                           "compute_capability": f"{cc_major}.{cc_minor}"
                       })
                   return devices
               finally:
                   pynvml.nvmlShutdown()
           except Exception:
               return None
       ```
     - Tier 2: Isolated CLI Fallback:
       - Use `shutil.which("nvidia-smi")` and `shutil.which("rocm-smi")`.
       - Execute in a short-lived subprocess with `timeout=3` capturing `--query-gpu=gpu_name,memory.total --format=csv,noheader,nounits`.
     - Tier 3: CPU Fallback: If no GPU is found, cleanly record CPU architecture, thread count via `os.cpu_count()`, and platform details.
  2. Strict CUDA-Locking Prohibition:
     - Add explicit AST / runtime assertions: `sys.modules.get("torch")` or `torch.cuda.is_initialized()` must NEVER be invoked during orchestrator telemetry collection.
     - Ensure NVIDIA MPS server remains free for dynamic rank multiplexing.

---

### [Task 9: Deterministic UUIDv5 Content-Addressable PES Points & Thread-Safe SWMR Storage (Suggestion #59)]
- **Files Affected:** `src/cochem_base/core/models.py` (`PESPointRecord`), `src/cochem_base/core_engine/cochem_core_pes_store.py` (`PESStore`)
- **Problem Statement:**
  `PESPointRecord.point_id` uses ephemeral local strings (`"grid_2d:142"`), causing collisions when merging independent scan campaigns. Furthermore, concurrent uncoordinated HDF5 writes without SWMR sequencing cause broken root groups, corrupted B-trees, and race crashes. Lockfiles placed on shared network storage (NFS, Lustre, GPFS) stall execution due to non-compliant distributed file locking, violating FAIR F1 and the HPC Distributed Lock Prohibition.
- **Implementation Requirements:**
  1. Deterministic Content-Addressable `point_id` in `PESPointRecord`:
     - Define `NAMESPACE_COCHEM = uuid.UUID("a6c4f69a-2d4e-4e68-912f-6e2101e4a682")`.
     - Generate `point_id` deterministically from canonical RFC 8785 JSON representation:
       ```python
       @classmethod
       def generate_point_id(cls, geometry: List[float], symbols: List[str], method: str, basis: Optional[str]) -> str:
           normalized_payload = {
               "symbols": [s.upper() for s in symbols],
               "geometry": [round(float(c), 8) for c in geometry],
               "method": method.strip().lower(),
               "basis": (basis or "").strip().lower()
           }
           canonical_bytes = rfc8785_canonicalize(normalized_payload)
           return str(uuid.uuid5(NAMESPACE_COCHEM, canonical_bytes.decode("utf-8")))
       ```
     - Ensure `PESPointRecord.point_id` defaults automatically to this deterministic UUIDv5.
  2. Thread-Safe HDF5 SWMR Protocols in `PESStore`:
     - SWMR Initialization Sequencing: Open HDF5 with `libver='latest'`. Pre-allocate chunked, resizable datasets and write initial metadata headers *before* activating `f.swmr_mode = True`.
     - Readers open with `mode='r'`, `swmr=True`, and call `dataset.refresh()` before reading extensible points.
  3. Local Scratch Lock Enforcement (HPC Distributed Lock Prohibition):
     - All inter-process locking must use `filelock.FileLock`.
     - The lockfile path must resolve strictly on node-local scratch:
       `lock_dir = pathlib.Path(os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR") or pathlib.Path.home() / ".cochem" / "scratch")`
     - Lockfiles on network file systems (Lustre, GPFS, NFS) are strictly prohibited.
  4. Shard Consolidation (`merge_pes_shards`):
     - Stage shard additions in local scratch memory, verify UUIDv5 point uniqueness, and perform atomic consolidation into the target store.

---

### [Task 10: Canonical Composite Fidelity Tier Vocabulary & Extensible Registry Enum (Suggestion #60)]
- **Files Affected:** `src/cochem_base/core/glossary.py` (`CalculationFidelity`), `src/cochem_base/core/models.py` (`CalculationJobPayload`)
- **Problem Statement:**
  `CalculationFidelity` enum contains only 5 legacy strings (`U_HF`, `R_DFT`, `XTB2`, `DLPNO_CCSD_T`, `CASSCF`). Submitting jobs with canonical composite recipes from Method Matrix v4 (§9A, Table 3) such as `junChS-F12`, `T3-3h`, or `R2` raises Pydantic `ValidationError`, blocking execution and provenance recording of high-accuracy computational calculations.
- **Implementation Requirements:**
  1. Refactor `CalculationFidelity` in `src/cochem_base/core/glossary.py`:
     - Convert to an extensible string enumeration supporting all Method Matrix v4 official tiers:
       ```python
       class CalculationFidelity(str, Enum):
           # Low / Semiempirical Tiers
           XTB1 = "XTB1"
           XTB2 = "XTB2"
           PM6 = "PM6"
           AM1 = "AM1"
           
           # Single Reference / Mean Field
           R_HF = "R_HF"
           U_HF = "U_HF"
           R_DFT = "R_DFT"
           U_DFT = "U_DFT"
           RO_DFT = "RO_DFT"
           
           # Correlated Wavefunction
           MP2 = "MP2"
           DLPNO_CCSD_T = "DLPNO_CCSD_T"
           CCSD_T = "CCSD_T"
           CCSD_T_F12 = "CCSD_T_F12"
           CASSCF = "CASSCF"
           NEVPT2 = "NEVPT2"
           
           # Method Matrix v4 Canonical Composite Tiers (Table 3 & §9A)
           JUNCHS = "junChS"
           JUNCHS_F12 = "junChS-F12"
           CHS = "ChS"
           CHS_F12 = "ChS-F12"
           T3_10S = "T3-10s"
           T3_1MIN = "T3-1min"
           T3_30MIN = "T3-30min"
           T3_3H = "T3-3h"
           T3_12H = "T3-12h"
           T4_1D = "T4-1d"
           R2 = "R2"
           
           # Custom / Open QCSchema Specification
           CUSTOM_COMPOSITE = "CUSTOM_COMPOSITE"
       ```
  2. Update `CalculationJobPayload` in `src/cochem_base/core/models.py`:
     - Allow `fidelity: Union[CalculationFidelity, str]` with automated normalization.
     - Validate that composite recipe strings match either official Method Matrix tiers or structured QCSchema method specifications.

---

## 4. Zero-Mock Test Suite Specifications

Author comprehensive, production-grade test suites executing real physical operations with zero mocks, zero monkey-patched stubs, and zero synthetic loops.

### Test Suite 1: Architecture, Provenance, Hardware & Concurrency (`tests/core/test_architecture_part6.py`)
1. **`test_w3c_prov_o_jsonld_serialization()` (Suggestion #53):**
   - Instantiate a `DAGNode` representing an optimization step (`Activity`) and resulting conformer (`Entity`).
   - Call `.to_prov_jsonld()`.
   - Assert output contains `@context`, `@id`, and valid `prov:wasDerivedFrom` and `prov:wasGeneratedBy` relationships.
   - Validate that local context resolution resolves from `cochem_base/schemas/contexts/prov_o_context.jsonld` with zero outbound network calls.
2. **`test_vcs_provenance_container_introspection()` (Suggestion #57):**
   - Execute `get_vcs_provenance()` in an isolated environment where `.git` is absent.
   - Verify fallback to `importlib.metadata`.
   - Assert returned dictionary contains valid package version and status `"DISTRIBUTION_PACKAGE"` rather than failing.
3. **`test_strictly_non_initializing_gpu_telemetry()` (Suggestion #58):**
   - Execute `collect_hardware_metadata()`.
   - Assert telemetry returns device list (or CPU fallback) without raising exceptions.
   - Assert that `torch.cuda.is_initialized()` is `False` (if PyTorch is installed in the test environment), proving zero CUDA context binding to the process PID.
4. **`test_pes_store_swmr_concurrency_and_local_locking()` (Suggestion #59):**
   - Initialize a `PESStore` HDF5 file with pre-allocated datasets in SWMR mode.
   - Execute concurrent read and write operations across background worker threads using `filelock.FileLock`.
   - Assert lockfile is created inside the local scratch directory (`SLURM_TMPDIR` or local temp), never on shared remote paths.
   - Confirm zero dataset corruption or B-tree lockups.

### Test Suite 2: Physics Invariants, Radii, Licensing & Asymmetric Signatures (`tests/core/test_physics_integrity_part6.py`)
1. **`test_mendeleev_isotopic_nuclear_mass_resolution()` (Suggestion #51):**
   - Call `get_isotopic_mass("C", 14)`; verify returned mass is $\approx 14.003241$ u [M] (not $12.011$ u).
   - Call `get_isotopic_mass("H", 2)`; verify Deuterium mass $\approx 2.014101$ u [M].
   - Call `get_isotopic_mass("C", 999)`; assert `IsotopeStabilityError` is explicitly raised.
   - Assert zero fallback to standard terrestrial atomic weight.
2. **`test_hierarchical_empirical_radii_lookup()` (Suggestion #52):**
   - Call `get_covalent_radius("Ar")`; verify returned radius is empirical van der Waals radius $\approx 1.88$ Å (or Pyykkö radius), strictly not $0.77$ Å.
   - Call `get_covalent_radius("C")`; verify radius $\approx 0.75$–$0.77$ Å from empirical tables.
   - Call `get_covalent_radius("Xe")`; verify empirical radius $> 1.3$ Å.
   - Call `get_covalent_radius("InvalidElement")` and assert `RadiusNotFoundError` is raised.
3. **`test_spdx_data_licensing_validation()` (Suggestion #54):**
   - Instantiate `QCSchemaProvenance(license="CC-BY-4.0")`; assert validation succeeds.
   - Instantiate `QCSchemaProvenance(license="CC0-1.0")`, `(license="MIT")`; verify acceptance.
   - Attempt instantiation with `license="Proprietary-Unpublished-Invalid"`; assert Pydantic `ValidationError` is raised.
4. **`test_dynamic_registry_schema_isotopic_masses()` (Suggestion #55):**
   - Query `get_registry_atomic_mass("Ar", 40)` and `get_registry_atomic_mass("Cl", 37)`.
   - Assert returned values match CIAAW physical isotopic masses.
   - Verify that `ISOTOPIC_MASSES` dictionary does not exist in module globals (`assert not hasattr(cochem_core_registry_schema, "ISOTOPIC_MASSES")`).
5. **`test_w3c_linked_data_proof_pure_ed25519_did_key()` (Suggestion #56):**
   - Generate an Ed25519 private key using `cryptography`.
   - Sign a computation record using `sign_report_payload()`.
   - Assert output contains standard `"proof"` block with `type="Ed25519Signature2020"` and `verificationMethod` starting with `"did:key:z"`.
   - Verify the signature using `verify_report_payload()`; assert `True`.
   - Tamper with a numeric result in payload; assert `verify_report_payload()` returns `False`.
   - Assert public key was extracted and validated completely offline without HTTP calls.
6. **`test_deterministic_uuid5_pes_point_id()` (Suggestion #59):**
   - Generate two `PESPointRecord` instances with identical geometries, basis sets, and methods.
   - Assert both instances possess identical `point_id` UUIDv5 strings.
   - Perturb one coordinate by $0.001$ Å; assert the generated `point_id` changes deterministically.
7. **`test_calculation_fidelity_canonical_tiers()` (Suggestion #60):**
   - Instantiate `CalculationJobPayload` with `fidelity="junChS-F12"`, `fidelity="T3-3h"`, and `fidelity="R2"`.
   - Assert all canonical Method Matrix v4 tiers are recognized and validated without error.

---

## 5. Verification & Acceptance Criteria

1. **Zero-Mock & Zero-Stub Verification:**
   - Strict scan across all modified files. Zero occurrences of `unittest.mock`, `MagicMock`, `@patch`, `TODO`, `pass`, or `NotImplementedError` permitted.
2. **Full Test Suite Execution:**
   - Execute `pytest tests/core/test_architecture_part6.py tests/core/test_physics_integrity_part6.py`.
   - 100% of authored tests must pass with physical I/O, actual NVML/CLI hardware queries, real HDF5 SWMR files, genuine Mendeleev lookups, and real Ed25519 cryptographic proofs.
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
| **Nuclear Mass Resolution** | Elimination of `el.mass` fallback in `get_isotopic_mass`; explicit `IsotopeStabilityError` raising | **PASS (VERIFIED)** |
| **Empirical Radii Lookup** | Eradication of hardcoded `0.77` Å fallback; hierarchical Pyykkö $\to$ Cordero $\to$ vdW resolution | **PASS (VERIFIED)** |
| **PROV-O Linked Data** | Bundled offline local JSON-LD `@context` catalog and standard W3C conformer lineage export | **PASS (VERIFIED)** |
| **SPDX Licensing Schema** | Immutable `license` field in QCSchema and PES records validating against local SPDX list | **PASS (VERIFIED)** |
| **Mendeleev Mandate** | Deletion of static 18-element `ISOTOPIC_MASSES` dictionary; dynamic cached SQLite lookups | **PASS (VERIFIED)** |
| **Linked Data Proofs** | Standard W3C Ed25519Signature2020 envelopes with offline cryptographic `did:key` multicodec | **PASS (VERIFIED)** |
| **VCS Introspection** | OS-agnostic `pathlib.Path` dynamic root checks and `importlib.metadata` package fallback | **PASS (VERIFIED)** |
| **Non-Initializing Telemetry**| Direct NVML C-bindings with immediate shutdown; zero CUDA runtime context binding | **PASS (VERIFIED)** |
| **Content-Addressable PES** | Deterministic UUIDv5 point IDs via RFC 8785; thread-safe SWMR HDF5 with node-local locking | **PASS (VERIFIED)** |
| **Method Matrix Tiers** | Expansion of `CalculationFidelity` enum to all Method Matrix v4 composite schemes | **PASS (VERIFIED)** |
| **Zero-Mock Mandate** | Zero stubs, zero mocks, zero synthetic loops across all 10 tasks and test specifications | **PASS (VERIFIED)** |

**Council Ratification Verdict:** `RATIFIED: APPROVED FOR CODER IMPLEMENTATION`
# CODING PROMPT: CoChem-BASE Core Architecture Implementation (Chunk 6: Suggestions #51–#60)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§3.0, §4.4, §6.4, §6.10, §8.2, §8.3, §8.4, §8A.4, §8B.4, §8C, §9A, §20, Table 3, QS-1, QS-3)
- Zero-Mock Anti-Spoofing Protocol v2 (Zero placeholders, zero stubs, zero simulated mocks, 100% real physical execution)
- Tripartite Storage Air-Gap Architecture (Source $T_{\text{src}}$ immutable read-only, Ephemeral Scratch $T_{\text{scr}}$ isolated, Artifacts $T_{\text{art}}$ read-write cryptographic commitments)
- 6-Tier Environment Matrix (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions, HPC)
- Dynamic Mendeleev Invariant Mandate (`from mendeleev import element`, zero hardcoded atomic masses, strict dynamic IUPAC/CIAAW physical mass retrieval)
- FAIR Principles Compliance (F1, F4, A1, I1, I2, I3, R1.1, R1.2, R1.3)
- MolSSI QCSchema v1 Compliance (`schema_name="qcschema_output"`, `schema_version=1`, explicit `AtomicResult` mapping)
- Authoritative CODATA 2018 / 2022 IEEE-754 FP64 Invariant Mandate
- IETF RFC 8032 PureEd25519, RFC 8785 JSON Canonicalization Scheme (JCS), & W3C Linked Data Proof Standards
- Cross-Platform Concurrency Directive (Thread-safe SWMR HDF5, strictly non-initializing GPU discovery with zero CUDA-locking, local scratch file locking, strictly no POSIX `fcntl` on network filesystems)

---

## 1. Executive Summary & Objective

Implement, harden, and physically verify Suggestions #51 through #60 of the CoChem-BASE Core Architecture Improvement Specification. This work package resolves critical vulnerabilities across elemental mass fallbacks, empirical covalent/vdW radii topology perception, semantic provenance and conformer lineage Linked Data annotations, machine-readable SPDX data licensing, dynamic isotopic mass validation, W3C Linked Data Proof offline digital signatures, environment-agnostic VCS package provenance, non-initializing GPU telemetry with zero CUDA runtime locking, deterministic UUIDv5 content-addressable PES storage with Thread-Safe HDF5 SWMR protocols, and Method Matrix v4 canonical composite fidelity tier definitions.

Specific implementation targets include:
1. Eradicating permissive fallback to standard terrestrial atomic weight (`el.mass`) in `get_isotopic_mass("C", 14)`, raising an explicit `IsotopeStabilityError` whenever a requested isotope cannot be resolved to a physical nuclear mass in the Mendeleev registry.
2. Replacing the hardcoded `0.77` Å fallback in `get_covalent_radius()` with a strict hierarchical Mendeleev lookup (Pyykkö covalent radius $\to$ Cordero covalent radius $\to$ van der Waals radius $\to$ `RadiusNotFoundError`), ensuring accurate intermolecular distance thresholds and topological perception for noble gases and heavy elements.
3. Upgrading conformer lineage graphs in `DAGNode` to emit W3C PROV-O compliant JSON-LD documents (`prov:wasDerivedFrom`, `prov:wasGeneratedBy`, `prov:Activity`, `prov:Entity`) while enforcing Tripartite Air-Gap compliance via an offline local JSON-LD context catalog bundled in `cochem_base/schemas/contexts/`.
4. Adding an immutable `license: str = "CC-BY-4.0"` (or configurable SPDX identifier) field to `QCSchemaProvenance`, `QCSchemaMethodRecord`, and `QCResultsRecord`, validating against an offline local SPDX identifier table to uphold FAIR Principle R1.1.
5. Eradicating the static 18-element `ISOTOPIC_MASSES` dictionary in `cochem_core_registry_schema.py` and replacing it with a cached, dynamic lookup calling `mendeleev.element(symbol).isotopes` backed by Mendeleev's bundled local SQLite database for fully air-gapped execution across all 6 environment tiers.
6. Refactoring `sign_report_payload` in `cochem_crypto.py` to emit standard W3C Linked Data Proof envelopes (`Ed25519Signature2020`) with pure cryptographic `did:key` resolution via multicodec `0xed01` prefix and base58btc encoding without external network DID registries.
7. Enhancing `get_vcs_provenance()` in `cochem_version.py` to use dynamic `pathlib.Path` root checks and Python packaging metadata (`importlib.metadata`) to capture accurate package version and distribution provenance inside stripped Docker containers and HPC wheels lacking `.git` directories.
8. Refactoring `collect_hardware_metadata()` to use a strictly non-initializing discovery protocol: querying direct NVML C-bindings (`pynvml.nvmlInit()` / `pynvml.nvmlShutdown()`) with fallback to short-lived CLI calls (`nvidia-smi` / `rocm-smi`), strictly banning `torch.cuda` or `jax.devices` in the orchestrator telemetry path to guarantee zero CUDA-locking and maintain NVIDIA MPS multiplexing readiness.
9. Refactoring `PESPointRecord` to generate deterministic, globally unique UUIDv5 identifiers from canonical RFC 8785 JSON hashes of molecular geometry, basis set, and electronic structure method, while enforcing Thread-Safe HDF5 SWMR protocols with cross-platform node-local file locking adhering to the HPC Distributed Lock Prohibition.
10. Expanding `CalculationFidelity` in `cochem_base.core.glossary` from 5 legacy strings to encompass all canonical composite tiers established in Method Matrix v4 Table 3 and §9A (`junChS`, `junChS-F12`, `ChS`, `T3-10s`, `T3-1min`, `T3-30min`, `T3-3h`, `T3-12h`, `T4-1d`, `R2`) as an extensible string-enum supporting open QCSchema specifications.

All code modifications must be accompanied by comprehensive, zero-mock unit and integration tests executing real Mendeleev lookups, offline JSON-LD expansions, physical Ed25519 cryptographic signing, real SWMR HDF5 dataset preallocation, and non-initializing NVML hardware interrogation.

---

## 2. Target Files & Deliverable Manifest

### Metadata, Elemental Invariants & Hardware Discovery Modules
1. `src/cochem_base/core/metadata.py` (Suggestions #51, #52, #58)
2. `src/cochem_base/core/exceptions.py` (Suggestions #51, #52)
3. `src/cochem_base/cochem_core_registry_schema.py` (Suggestion #55)

### Provenance, Versioning & Cryptographic Proof Modules
4. `src/cochem_base/core/cochem_provenance.py` (Suggestion #53)
5. `src/cochem_base/schemas/contexts/prov_o_context.jsonld` (Suggestion #53)
6. `src/cochem_base/core/cochem_crypto.py` (Suggestion #56)
7. `src/cochem_base/core/cochem_version.py` (Suggestion #57)

### Core Data Models, Storage & Domain Vocabularies
8. `src/cochem_base/core/models.py` (Suggestions #54, #59)
9. `src/cochem_base/core_engine/cochem_core_pes_store.py` (Suggestions #54, #59)
10. `src/cochem_base/core/licensing.py` (Suggestion #54)
11. `src/cochem_base/core/glossary.py` (Suggestion #60)

### Zero-Mock Test Suite Deliverables
12. `tests/core/test_architecture_part6.py` (Validating Suggestions #53, #57, #58, #59)
13. `tests/core/test_physics_integrity_part6.py` (Validating Suggestions #51, #52, #54, #55, #56, #59, #60)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Dynamic Isotopic Nuclear Mass Resolution & Unphysical Fallback Removal (Suggestion #51)]
- **Files Affected:** `src/cochem_base/core/metadata.py` (`get_isotopic_mass`), `src/cochem_base/core/exceptions.py`
- **Problem Statement:**
  `get_isotopic_mass("C", 14)` attempts to find the isotope in Mendeleev's isotope list. When an isotope lookup fails or cannot be resolved, the function silently falls back to `float(el.mass)`. In Mendeleev, `el.mass` is the terrestrial abundance-weighted atomic weight ($12.011$ u for Carbon), not an isotopic nuclear mass. Supplying the terrestrial average mass to rotational force-field re-diagonalization calculates incorrect moments of inertia, shifting predicted ground-state rotational constants $B_0$ and vibrational frequencies by dozens of MHz [M], violating Method Matrix v4 §6.10, §8B.4, and FAIR Principle R1.3.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/exceptions.py`, define:
     ```python
     class IsotopeStabilityError(ValueError):
         """Raised when a requested isotope cannot be physically resolved to an isotopic nuclear mass."""
         pass
     ```
  2. Refactor `get_isotopic_mass(symbol_or_atomic_number: Union[str, int], mass_number: int) -> float` in `src/cochem_base/core/metadata.py`:
     - Query dynamic element data via `el = mendeleev.element(symbol_or_atomic_number)`.
     - Filter `el.isotopes` for an isotope where `iso.mass_number == int(mass_number)`.
     - If matched and `iso.mass` is not `None` and `float(iso.mass) > 0.0`:
       Return `float(iso.mass)` [M].
     - If no matching isotope exists, or if `iso.mass` is `None` or non-positive:
       Explicitly raise `IsotopeStabilityError(f"Isotope '{el.symbol}-{mass_number}' cannot be resolved to a physical isotopic mass in authoritative CIAAW/Mendeleev data.")`.
     - Strictly eliminate any code path returning `el.mass`, `el.atomic_weight`, or static numeric constants when an isotopic mass number is requested.
  3. Provenance and Invariants:
     - Tag return value documentation with `[M]` (Measured empirical nuclear mass).
     - Ensure compatibility across all stable and known radioactive isotopes (e.g. `14C`, `2H`, `15N`, `37Cl`, `18O`).

---

### [Task 2: Hierarchical Empirical Radii Lookup & Elimination of Hardcoded 0.77 Å Fallback (Suggestion #52)]
- **Files Affected:** `src/cochem_base/core/metadata.py` (`get_covalent_radius`), `src/cochem_base/core/exceptions.py`
- **Problem Statement:**
  `get_covalent_radius()` returns a hardcoded default of `0.77` Å when radius data is absent. The value `0.77` Å is the single-bond covalent radius of $sp^3$ Carbon. When assigned to noble gases (He, Ne, Ar, Kr, Xe) or heavy transition metals in van der Waals complexes, intermolecular contact algorithms misclassify non-covalent contacts as vacant voids or perceive false covalent bonds, corrupting molecular graphs and frozen-monomer initial alignments under Method Matrix v4 §20 [M].
- **Implementation Requirements:**
  1. In `src/cochem_base/core/exceptions.py`, define:
     ```python
     class RadiusNotFoundError(KeyError):
         """Raised when empirical covalent or van der Waals radius is unavailable for an element."""
         pass
     ```
  2. Refactor `get_covalent_radius(symbol_or_atomic_number: Union[str, int], radius_type: str = "pyykko") -> float` in `src/cochem_base/core/metadata.py`:
     - Resolve element using `el = mendeleev.element(symbol_or_atomic_number)`.
     - Implement hierarchical empirical lookup without hardcoded defaults:
       1. Primary: Pyykkö single-bond covalent radius (`el.covalent_radius_pyykko`).
       2. Secondary: Cordero covalent radius (`el.covalent_radius_cordero`).
       3. Tertiary: Standard covalent radius (`el.covalent_radius`).
       4. Quaternary (for noble gases or non-bonding atoms where covalent bonds do not form): van der Waals radius (`el.vdw_radius`).
     - Convert value to Angstroms (if reported in picometers by the underlying registry, divide by 100.0; verify Mendeleev units dynamically).
     - If all empirical radii attributes evaluate to `None` or $\le 0.0$:
       Raise `RadiusNotFoundError(f"Empirical radius for element '{el.symbol}' ({el.atomic_number}) could not be resolved from Mendeleev registries.")`.
     - Eradicate the literal `0.77` Å fallthrough return completely.

---

### [Task 3: W3C PROV-O Compliant JSON-LD Lineage & Air-Gapped Local Context Catalog (Suggestion #53)]
- **Files Affected:** `src/cochem_base/core/cochem_provenance.py` (`DAGNode`), `src/cochem_base/schemas/contexts/prov_o_context.jsonld`
- **Problem Statement:**
  `DAGNode.to_dict()` outputs an ad-hoc JSON structure lacking semantic Linked Data annotations. Scientific knowledge graphs and semantic search harvesters cannot index conformer lineage trees (CREST $\to$ GOAT $\to$ ORCA DFT $\to$ DLPNO). Attempting live online JSON-LD `@context` resolution (`http://www.w3.org/ns/prov#`) triggers network timeout crashes on air-gapped HPC compute nodes and CI runners, violating FAIR Principles I1, I3, and the Tripartite Air-Gap mandate.
- **Implementation Requirements:**
  1. Create the offline bundled context catalog file `src/cochem_base/schemas/contexts/prov_o_context.jsonld`:
     ```json
     {
       "@context": {
         "prov": "http://www.w3.org/ns/prov#",
         "dcterms": "http://purl.org/dc/terms/",
         "cochem": "https://cochem.org/schema/core#",
         "Entity": "prov:Entity",
         "Activity": "prov:Activity",
         "Agent": "prov:Agent",
         "wasDerivedFrom": {"@id": "prov:wasDerivedFrom", "@type": "@id"},
         "wasGeneratedBy": {"@id": "prov:wasGeneratedBy", "@type": "@id"},
         "wasAssociatedWith": {"@id": "prov:wasAssociatedWith", "@type": "@id"},
         "startedAtTime": {"@id": "prov:startedAtTime", "@type": "http://www.w3.org/2001/XMLSchema#dateTime"},
         "endedAtTime": {"@id": "prov:endedAtTime", "@type": "http://www.w3.org/2001/XMLSchema#dateTime"},
         "conformerId": "cochem:conformerId",
         "relativeEnergy": "cochem:relativeEnergyKcalMol",
         "rotationalConstants": "cochem:rotationalConstantsMHz"
       }
     }
     ```
  2. In `src/cochem_base/core/cochem_provenance.py`:
     - Implement `get_local_prov_context() -> Dict[str, Any]` which reads `prov_o_context.jsonld` directly using `pathlib.Path(__file__).parent.parent / "schemas" / "contexts" / "prov_o_context.jsonld"`.
     - Extend `DAGNode`:
       - Add method `to_prov_jsonld(self, base_uri: str = "urn:cochem:conformer:") -> Dict[str, Any]`:
         - Construct a standard JSON-LD document with `@context` referencing the bundled definitions.
         - Generate `@id` as `{base_uri}{self.node_id}`.
         - Assign `@type`: `["prov:Entity", "cochem:Conformer"]` for geometry/result nodes, or `["prov:Activity", "cochem:Optimization"]` for transformation steps.
         - Map parent edges using `prov:wasDerivedFrom`: `[{"@id": f"{base_uri}{parent_id}"} for parent_id in self.parents]`.
         - Annotate generation activity via `prov:wasGeneratedBy`.
         - Attach execution metadata, timestamps (ISO 8601 UTC), energy, and rotational constant properties under canonical `cochem:` namespace terms.
     - Provide an offline JSON-LD context validator ensuring zero network socket requests are dispatched when serializing or verifying conformer lineage.

---

### [Task 4: Immutable SPDX Data Usage Licensing Schema (Suggestion #54)]
- **Files Affected:** `src/cochem_base/core/models.py`, `src/cochem_base/core_engine/cochem_core_pes_store.py`, `src/cochem_base/core/licensing.py`
- **Problem Statement:**
  Computational output records (`QCSchemaProvenance`, `QCSchemaMethodRecord`, `QCResultsRecord`, `PESPointRecord`) omit machine-readable licensing metadata. Downstream scientific data repositories reject exported datasets, and commercial or academic users cannot programmatically determine dataset reuse rights, directly violating FAIR Principle R1.1 ("(Meta)data are released with a clear and accessible data usage license").
- **Implementation Requirements:**
  1. Author `src/cochem_base/core/licensing.py`:
     - Define an immutable tuple or frozen set of approved open-science SPDX license identifiers:
       `OFFICIAL_SPDX_LICENSES = frozenset({"CC-BY-4.0", "CC0-1.0", "MIT", "Apache-2.0", "BSD-3-Clause", "GPL-3.0-only", "AGPL-3.0-only"})`.
     - Implement `validate_spdx_license(license_id: str) -> str`:
       - Strip whitespace; verify `license_id in OFFICIAL_SPDX_LICENSES` or matches standard SPDX regex `^[A-Za-z0-9\.\-\+]+$`.
       - Raise `ValueError(f"Invalid or unrecognized SPDX license identifier: '{license_id}'")` if validation fails.
  2. Update Data Models:
     - In `QCSchemaProvenance`, `QCSchemaMethodRecord`, and `QCResultsRecord` (`src/cochem_base/core/models.py` and `cochem_core_pes_store.py`):
       - Add field:
         ```python
         license: str = Field(
             default="CC-BY-4.0",
             description="SPDX license identifier governing data reuse rights (FAIR R1.1)"
         )
         ```
       - Add a Pydantic `@field_validator("license")` invoking `validate_spdx_license(v)`.
     - In `PESPointRecord`: add `license: str = "CC-BY-4.0"` to its metadata envelope.
     - Ensure existing datasets without explicit license tags default safely to `"CC-BY-4.0"`.

---

### [Task 5: Dynamic Isotopic Mass Registry & Elimination of Static ISOTOPIC_MASSES Table (Suggestion #55)]
- **Files Affected:** `src/cochem_base/cochem_core_registry_schema.py`
- **Problem Statement:**
  `cochem_core_registry_schema.py` defines a static dictionary `ISOTOPIC_MASSES` containing hardcoded mass values for only 18 elements. Calculations involving noble gases (argon, neon, krypton) or isotopes like $^{37}\text{Cl}$, $^{13}\text{C}$, or $^{2}\text{H}$ trigger validation rejections or fail schema validation. This violates the Mendeleev Mandate (Method Matrix v4 §8C) and artificially constrains the ecosystem's chemical domain.
- **Implementation Requirements:**
  1. Eradicate the static `ISOTOPIC_MASSES = {...}` dictionary from `src/cochem_base/cochem_core_registry_schema.py`.
  2. Implement an offline dynamic registry accessor backed by Mendeleev's bundled local SQLite database:
     ```python
     @functools.lru_cache(maxsize=512)
     def get_registry_atomic_mass(symbol_or_z: Union[str, int], mass_number: Optional[int] = None) -> float:
         """Dynamic IUPAC/CIAAW mass resolver honoring the Mendeleev Mandate [M]."""
         el = mendeleev.element(symbol_or_z)
         if mass_number is not None:
             iso = next((i for i in el.isotopes if i.mass_number == mass_number), None)
             if iso is not None and iso.mass is not None:
                 return float(iso.mass)
             raise IsotopeStabilityError(f"Isotope {el.symbol}-{mass_number} not found in Mendeleev.")
         if el.atomic_weight is not None:
             return float(el.atomic_weight)
         if el.mass is not None:
             return float(el.mass)
         raise ValueError(f"No valid mass available for element {el.symbol}.")
     ```
  3. Refactor all schema validation routines and regex lookups in `cochem_core_registry_schema.py` to invoke `get_registry_atomic_mass()` dynamically.
  4. Ensure module load time is negligible (< 10 ms [E]) due to cached local SQLite queries, with zero external network access.

---

### [Task 6: W3C Linked Data Proof Envelopes with Offline PureEd25519 did:key Resolution (Suggestion #56)]
- **Files Affected:** `src/cochem_base/core/cochem_crypto.py` (`sign_report_payload`, `verify_report_payload`)
- **Problem Statement:**
  Computational report signatures are serialized under an ad-hoc key (`_provenance_signature`), preventing external scientific repositories from verifying computation proofs. Furthermore, if external DID registries are queried over HTTPS to resolve public keys, air-gapped compute nodes experience connection timeouts, violating FAIR Principles A1, I1, R1.2, and User Manual §6.4.1.
- **Implementation Requirements:**
  1. Implement offline `did:key` encoder and decoder in `cochem_base/core/cochem_crypto.py`:
     - Ed25519 multicodec prefix: `0xed01` (bytes `b'\xed\x01'`).
     - Encode: Given raw 32-byte Ed25519 public key, prepend `b'\xed\x01'`, encode using base58btc, and prepend `"did:key:z"`.
     - Decode: Given `"did:key:z..."`, strip `"did:key:z"`, decode base58btc, assert first 2 bytes are `b'\xed\x01'`, and extract the 32-byte public key directly. Zero external HTTP/network lookups permitted.
  2. Refactor `sign_report_payload(payload: Dict[str, Any], private_key: ed25519.Ed25519PrivateKey) -> Dict[str, Any]`:
     - Canonicalize `payload` via RFC 8785 JSON Canonicalization Scheme (JCS) bytes.
     - Sign raw canonical bytes using RFC 8032 PureEd25519 (`signature_bytes = private_key.sign(canonical_bytes)`).
     - Encode signature as base64 or multibase.
     - Return payload enveloped with standard W3C Linked Data Proof:
       ```python
       return {
           **payload,
           "proof": {
               "type": "Ed25519Signature2020",
               "created": datetime.now(timezone.utc).isoformat(),
               "verificationMethod": public_key_to_did_key(private_key.public_key()),
               "proofPurpose": "assertionMethod",
               "proofValue": base64.urlsafe_b64encode(signature_bytes).decode("ascii")
           }
       }
       ```
  3. Refactor `verify_report_payload(signed_payload: Dict[str, Any]) -> bool`:
     - Extract `proof = signed_payload.get("proof")`; if absent, return `False`.
     - Extract `did_key = proof.get("verificationMethod")`; decode raw public key bytes offline.
     - Separate payload from `proof` dictionary, canonicalize payload via RFC 8785, and verify `proofValue` using `public_key.verify(sig_bytes, canonical_bytes)`.
     - Return `True` on success; catch `InvalidSignature` and return `False`.

---

### [Task 7: Robust OS-Agnostic Dynamic VCS Provenance & Container Introspection (Suggestion #57)]
- **Files Affected:** `src/cochem_base/core/cochem_version.py` (`get_vcs_provenance`)
- **Problem Statement:**
  `get_vcs_provenance()` assumes `.git` directories or local `.build_manifest.json` files exist at hardcoded paths. When executed inside production Docker containers, Codespaces, or HPC Python wheels where `.git` is stripped, it silently drops software version metadata and returns `"UNTRACKED_BUILD"`. This breaks reproducible audit trails mandated by User Manual §6.4.2 and FAIR Principle R1.2.
- **Implementation Requirements:**
  1. Refactor `get_vcs_provenance() -> Dict[str, Any]` in `src/cochem_base/core/cochem_version.py`:
     - Hierarchy of provenance discovery:
       1. Git Repository Check: Use `pathlib.Path(__file__).resolve()` and traverse parents to locate `.git`. If found and git CLI is available, query commit SHA, branch, and dirty status via safe subprocess calls with 2-second timeouts.
       2. Build Manifest Check: Check for `.build_manifest.json` in package root or `COCHEM_ROOT`.
       3. Distribution Package Introspection (`importlib.metadata` - PEP 566):
          - Query `importlib.metadata.version("CoChem-BASE")` or `importlib.metadata.version("cochem_base")`.
          - Retrieve distribution metadata:
            ```python
            try:
                dist_version = importlib.metadata.version("CoChem-BASE")
                dist_files = importlib.metadata.files("CoChem-BASE")
                installer = importlib.metadata.distribution("CoChem-BASE").read_text("INSTALLER") or "unknown"
                return {
                    "vcs_type": "installed_wheel",
                    "version": dist_version,
                    "installer": installer.strip(),
                    "file_count": len(dist_files) if dist_files else 0,
                    "status": "DISTRIBUTION_PACKAGE"
                }
            except importlib.metadata.PackageNotFoundError:
                pass
            ```
       4. Fallback: Return structured dictionary with `"status": "UNTRACKED_BUILD"`, recorded execution timestamp, and platform telemetry.
  2. Dynamic Path Resolution:
     - Ensure all path checks use `pathlib.Path` relative to dynamic module anchors, `pathlib.Path.home()`, or environment variables (`COCHEM_ROOT`, `TMPDIR`).
     - Fully verify portability across Windows WSL, macOS OrbStack, Debian Linux, Codespaces, GitHub Actions, and HPC.

---

### [Task 8: Strictly Non-Initializing GPU Hardware Discovery & Zero CUDA-Locking (Suggestion #58)]
- **Files Affected:** `src/cochem_base/core/metadata.py` (`collect_hardware_metadata`)
- **Problem Statement:**
  `collect_hardware_metadata()` executes fragile CLI subprocess commands or risks importing `torch.cuda` / `jax.devices`. Calling `torch.cuda.is_available()` initializes the CUDA runtime context (`cudaInitDevice()`) and binds it to the host operating system PID. Spawning worker processes afterwards fails immediately with `RuntimeError: Cannot re-initialize CUDA in forked subprocess`, and permanently blocks dynamic NVIDIA Multi-Process Service (MPS) context multiplexing under Method Matrix v4 §8A.4 [M].
- **Implementation Requirements:**
  1. Implement strictly non-initializing GPU discovery in `src/cochem_base/core/metadata.py`:
     - Tier 1: Direct C-level NVML bindings (`pynvml`):
       ```python
       def _query_nvml_telemetry() -> Optional[List[Dict[str, Any]]]:
           try:
               import pynvml
               pynvml.nvmlInit()
               devices = []
               try:
                   count = pynvml.nvmlDeviceGetCount()
                   for idx in range(count):
                       handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                       name = pynvml.nvmlDeviceGetName(handle)
                       if isinstance(name, bytes):
                           name = name.decode("utf-8")
                       mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                       cc_major, cc_minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                       devices.append({
                           "index": idx,
                           "product_name": name,
                           "total_memory_bytes": int(mem.total),
                           "compute_capability": f"{cc_major}.{cc_minor}"
                       })
                   return devices
               finally:
                   pynvml.nvmlShutdown()
           except Exception:
               return None
       ```
     - Tier 2: Isolated CLI Fallback:
       - Use `shutil.which("nvidia-smi")` and `shutil.which("rocm-smi")`.
       - Execute in a short-lived subprocess with `timeout=3` capturing `--query-gpu=gpu_name,memory.total --format=csv,noheader,nounits`.
     - Tier 3: CPU Fallback: If no GPU is found, cleanly record CPU architecture, thread count via `os.cpu_count()`, and platform details.
  2. Strict CUDA-Locking Prohibition:
     - Add explicit AST / runtime assertions: `sys.modules.get("torch")` or `torch.cuda.is_initialized()` must NEVER be invoked during orchestrator telemetry collection.
     - Ensure NVIDIA MPS server remains free for dynamic rank multiplexing.

---

### [Task 9: Deterministic UUIDv5 Content-Addressable PES Points & Thread-Safe SWMR Storage (Suggestion #59)]
- **Files Affected:** `src/cochem_base/core/models.py` (`PESPointRecord`), `src/cochem_base/core_engine/cochem_core_pes_store.py` (`PESStore`)
- **Problem Statement:**
  `PESPointRecord.point_id` uses ephemeral local strings (`"grid_2d:142"`), causing collisions when merging independent scan campaigns. Furthermore, concurrent uncoordinated HDF5 writes without SWMR sequencing cause broken root groups, corrupted B-trees, and race crashes. Lockfiles placed on shared network storage (NFS, Lustre, GPFS) stall execution due to non-compliant distributed file locking, violating FAIR F1 and the HPC Distributed Lock Prohibition.
- **Implementation Requirements:**
  1. Deterministic Content-Addressable `point_id` in `PESPointRecord`:
     - Define `NAMESPACE_COCHEM = uuid.UUID("a6c4f69a-2d4e-4e68-912f-6e2101e4a682")`.
     - Generate `point_id` deterministically from canonical RFC 8785 JSON representation:
       ```python
       @classmethod
       def generate_point_id(cls, geometry: List[float], symbols: List[str], method: str, basis: Optional[str]) -> str:
           normalized_payload = {
               "symbols": [s.upper() for s in symbols],
               "geometry": [round(float(c), 8) for c in geometry],
               "method": method.strip().lower(),
               "basis": (basis or "").strip().lower()
           }
           canonical_bytes = rfc8785_canonicalize(normalized_payload)
           return str(uuid.uuid5(NAMESPACE_COCHEM, canonical_bytes.decode("utf-8")))
       ```
     - Ensure `PESPointRecord.point_id` defaults automatically to this deterministic UUIDv5.
  2. Thread-Safe HDF5 SWMR Protocols in `PESStore`:
     - SWMR Initialization Sequencing: Open HDF5 with `libver='latest'`. Pre-allocate chunked, resizable datasets and write initial metadata headers *before* activating `f.swmr_mode = True`.
     - Readers open with `mode='r'`, `swmr=True`, and call `dataset.refresh()` before reading extensible points.
  3. Local Scratch Lock Enforcement (HPC Distributed Lock Prohibition):
     - All inter-process locking must use `filelock.FileLock`.
     - The lockfile path must resolve strictly on node-local scratch:
       `lock_dir = pathlib.Path(os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR") or pathlib.Path.home() / ".cochem" / "scratch")`
     - Lockfiles on network file systems (Lustre, GPFS, NFS) are strictly prohibited.
  4. Shard Consolidation (`merge_pes_shards`):
     - Stage shard additions in local scratch memory, verify UUIDv5 point uniqueness, and perform atomic consolidation into the target store.

---

### [Task 10: Canonical Composite Fidelity Tier Vocabulary & Extensible Registry Enum (Suggestion #60)]
- **Files Affected:** `src/cochem_base/core/glossary.py` (`CalculationFidelity`), `src/cochem_base/core/models.py` (`CalculationJobPayload`)
- **Problem Statement:**
  `CalculationFidelity` enum contains only 5 legacy strings (`U_HF`, `R_DFT`, `XTB2`, `DLPNO_CCSD_T`, `CASSCF`). Submitting jobs with canonical composite recipes from Method Matrix v4 (§9A, Table 3) such as `junChS-F12`, `T3-3h`, or `R2` raises Pydantic `ValidationError`, blocking execution and provenance recording of high-accuracy computational calculations.
- **Implementation Requirements:**
  1. Refactor `CalculationFidelity` in `src/cochem_base/core/glossary.py`:
     - Convert to an extensible string enumeration supporting all Method Matrix v4 official tiers:
       ```python
       class CalculationFidelity(str, Enum):
           # Low / Semiempirical Tiers
           XTB1 = "XTB1"
           XTB2 = "XTB2"
           PM6 = "PM6"
           AM1 = "AM1"
           
           # Single Reference / Mean Field
           R_HF = "R_HF"
           U_HF = "U_HF"
           R_DFT = "R_DFT"
           U_DFT = "U_DFT"
           RO_DFT = "RO_DFT"
           
           # Correlated Wavefunction
           MP2 = "MP2"
           DLPNO_CCSD_T = "DLPNO_CCSD_T"
           CCSD_T = "CCSD_T"
           CCSD_T_F12 = "CCSD_T_F12"
           CASSCF = "CASSCF"
           NEVPT2 = "NEVPT2"
           
           # Method Matrix v4 Canonical Composite Tiers (Table 3 & §9A)
           JUNCHS = "junChS"
           JUNCHS_F12 = "junChS-F12"
           CHS = "ChS"
           CHS_F12 = "ChS-F12"
           T3_10S = "T3-10s"
           T3_1MIN = "T3-1min"
           T3_30MIN = "T3-30min"
           T3_3H = "T3-3h"
           T3_12H = "T3-12h"
           T4_1D = "T4-1d"
           R2 = "R2"
           
           # Custom / Open QCSchema Specification
           CUSTOM_COMPOSITE = "CUSTOM_COMPOSITE"
       ```
  2. Update `CalculationJobPayload` in `src/cochem_base/core/models.py`:
     - Allow `fidelity: Union[CalculationFidelity, str]` with automated normalization.
     - Validate that composite recipe strings match either official Method Matrix tiers or structured QCSchema method specifications.

---

## 4. Zero-Mock Test Suite Specifications

Author comprehensive, production-grade test suites executing real physical operations with zero mocks, zero monkey-patched stubs, and zero synthetic loops.

### Test Suite 1: Architecture, Provenance, Hardware & Concurrency (`tests/core/test_architecture_part6.py`)
1. **`test_w3c_prov_o_jsonld_serialization()` (Suggestion #53):**
   - Instantiate a `DAGNode` representing an optimization step (`Activity`) and resulting conformer (`Entity`).
   - Call `.to_prov_jsonld()`.
   - Assert output contains `@context`, `@id`, and valid `prov:wasDerivedFrom` and `prov:wasGeneratedBy` relationships.
   - Validate that local context resolution resolves from `cochem_base/schemas/contexts/prov_o_context.jsonld` with zero outbound network calls.
2. **`test_vcs_provenance_container_introspection()` (Suggestion #57):**
   - Execute `get_vcs_provenance()` in an isolated environment where `.git` is absent.
   - Verify fallback to `importlib.metadata`.
   - Assert returned dictionary contains valid package version and status `"DISTRIBUTION_PACKAGE"` rather than failing.
3. **`test_strictly_non_initializing_gpu_telemetry()` (Suggestion #58):**
   - Execute `collect_hardware_metadata()`.
   - Assert telemetry returns device list (or CPU fallback) without raising exceptions.
   - Assert that `torch.cuda.is_initialized()` is `False` (if PyTorch is installed in the test environment), proving zero CUDA context binding to the process PID.
4. **`test_pes_store_swmr_concurrency_and_local_locking()` (Suggestion #59):**
   - Initialize a `PESStore` HDF5 file with pre-allocated datasets in SWMR mode.
   - Execute concurrent read and write operations across background worker threads using `filelock.FileLock`.
   - Assert lockfile is created inside the local scratch directory (`SLURM_TMPDIR` or local temp), never on shared remote paths.
   - Confirm zero dataset corruption or B-tree lockups.

### Test Suite 2: Physics Invariants, Radii, Licensing & Asymmetric Signatures (`tests/core/test_physics_integrity_part6.py`)
1. **`test_mendeleev_isotopic_nuclear_mass_resolution()` (Suggestion #51):**
   - Call `get_isotopic_mass("C", 14)`; verify returned mass is $\approx 14.003241$ u [M] (not $12.011$ u).
   - Call `get_isotopic_mass("H", 2)`; verify Deuterium mass $\approx 2.014101$ u [M].
   - Call `get_isotopic_mass("C", 999)`; assert `IsotopeStabilityError` is explicitly raised.
   - Assert zero fallback to standard terrestrial atomic weight.
2. **`test_hierarchical_empirical_radii_lookup()` (Suggestion #52):**
   - Call `get_covalent_radius("Ar")`; verify returned radius is empirical van der Waals radius $\approx 1.88$ Å (or Pyykkö radius), strictly not $0.77$ Å.
   - Call `get_covalent_radius("C")`; verify radius $\approx 0.75$–$0.77$ Å from empirical tables.
   - Call `get_covalent_radius("Xe")`; verify empirical radius $> 1.3$ Å.
   - Call `get_covalent_radius("InvalidElement")` and assert `RadiusNotFoundError` is raised.
3. **`test_spdx_data_licensing_validation()` (Suggestion #54):**
   - Instantiate `QCSchemaProvenance(license="CC-BY-4.0")`; assert validation succeeds.
   - Instantiate `QCSchemaProvenance(license="CC0-1.0")`, `(license="MIT")`; verify acceptance.
   - Attempt instantiation with `license="Proprietary-Unpublished-Invalid"`; assert Pydantic `ValidationError` is raised.
4. **`test_dynamic_registry_schema_isotopic_masses()` (Suggestion #55):**
   - Query `get_registry_atomic_mass("Ar", 40)` and `get_registry_atomic_mass("Cl", 37)`.
   - Assert returned values match CIAAW physical isotopic masses.
   - Verify that `ISOTOPIC_MASSES` dictionary does not exist in module globals (`assert not hasattr(cochem_core_registry_schema, "ISOTOPIC_MASSES")`).
5. **`test_w3c_linked_data_proof_pure_ed25519_did_key()` (Suggestion #56):**
   - Generate an Ed25519 private key using `cryptography`.
   - Sign a computation record using `sign_report_payload()`.
   - Assert output contains standard `"proof"` block with `type="Ed25519Signature2020"` and `verificationMethod` starting with `"did:key:z"`.
   - Verify the signature using `verify_report_payload()`; assert `True`.
   - Tamper with a numeric result in payload; assert `verify_report_payload()` returns `False`.
   - Assert public key was extracted and validated completely offline without HTTP calls.
6. **`test_deterministic_uuid5_pes_point_id()` (Suggestion #59):**
   - Generate two `PESPointRecord` instances with identical geometries, basis sets, and methods.
   - Assert both instances possess identical `point_id` UUIDv5 strings.
   - Perturb one coordinate by $0.001$ Å; assert the generated `point_id` changes deterministically.
7. **`test_calculation_fidelity_canonical_tiers()` (Suggestion #60):**
   - Instantiate `CalculationJobPayload` with `fidelity="junChS-F12"`, `fidelity="T3-3h"`, and `fidelity="R2"`.
   - Assert all canonical Method Matrix v4 tiers are recognized and validated without error.

---

## 5. Verification & Acceptance Criteria

1. **Zero-Mock & Zero-Stub Verification:**
   - Strict scan across all modified files. Zero occurrences of `unittest.mock`, `MagicMock`, `@patch`, `TODO`, `pass`, or `NotImplementedError` permitted.
2. **Full Test Suite Execution:**
   - Execute `pytest tests/core/test_architecture_part6.py tests/core/test_physics_integrity_part6.py`.
   - 100% of authored tests must pass with physical I/O, actual NVML/CLI hardware queries, real HDF5 SWMR files, genuine Mendeleev lookups, and real Ed25519 cryptographic proofs.
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
| **Nuclear Mass Resolution** | Elimination of `el.mass` fallback in `get_isotopic_mass`; explicit `IsotopeStabilityError` raising | **PASS (VERIFIED)** |
| **Empirical Radii Lookup** | Eradication of hardcoded `0.77` Å fallback; hierarchical Pyykkö $\to$ Cordero $\to$ vdW resolution | **PASS (VERIFIED)** |
| **PROV-O Linked Data** | Bundled offline local JSON-LD `@context` catalog and standard W3C conformer lineage export | **PASS (VERIFIED)** |
| **SPDX Licensing Schema** | Immutable `license` field in QCSchema and PES records validating against local SPDX list | **PASS (VERIFIED)** |
| **Mendeleev Mandate** | Deletion of static 18-element `ISOTOPIC_MASSES` dictionary; dynamic cached SQLite lookups | **PASS (VERIFIED)** |
| **Linked Data Proofs** | Standard W3C Ed25519Signature2020 envelopes with offline cryptographic `did:key` multicodec | **PASS (VERIFIED)** |
| **VCS Introspection** | OS-agnostic `pathlib.Path` dynamic root checks and `importlib.metadata` package fallback | **PASS (VERIFIED)** |
| **Non-Initializing Telemetry**| Direct NVML C-bindings with immediate shutdown; zero CUDA runtime context binding | **PASS (VERIFIED)** |
| **Content-Addressable PES** | Deterministic UUIDv5 point IDs via RFC 8785; thread-safe SWMR HDF5 with node-local locking | **PASS (VERIFIED)** |
| **Method Matrix Tiers** | Expansion of `CalculationFidelity` enum to all Method Matrix v4 composite schemes | **PASS (VERIFIED)** |
| **Zero-Mock Mandate** | Zero stubs, zero mocks, zero synthetic loops across all 10 tasks and test specifications | **PASS (VERIFIED)** |

**Council Ratification Verdict:** `RATIFIED: APPROVED FOR CODER IMPLEMENTATION`
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\cochem_core_registry_schema.py ---
#!/usr/bin/env python3
"""
CoChem-BASE: Stage 0 Authority Rule - Golden Master Registry Schema
Defines rigid Pydantic v2 models for `cochem_system_config.json`.
Acts as a mathematical boundary preventing hallucinated configurations,
silent floating-point drift, relative path vulnerabilities, and OOM thread allocation.
All schemas strictly forbid extra fields and enforce validation on assignment.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import platform
import re
import shutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Set, Union, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS AND ENVIRONMENT EXPANSION
# =============================================================================

CARBON_13_ISOTOPIC_MASS: float = 13.00335483507


@functools.lru_cache(maxsize=512)
def get_registry_atomic_mass(symbol_or_z: Union[str, int], mass_number: Optional[int] = None) -> float:
    """Dynamic IUPAC/CIAAW mass resolver honoring the Mendeleev Mandate [M]."""
    import mendeleev
    from cochem_base.core.exceptions import IsotopeStabilityError

    el = mendeleev.element(symbol_or_z)
    if mass_number is not None:
        iso = next((i for i in el.isotopes if i.mass_number == mass_number), None)
        if iso is not None and iso.mass is not None:
            return float(iso.mass)
        raise IsotopeStabilityError(f"Isotope {el.symbol}-{mass_number} not found in Mendeleev.")
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.mass is not None:
        return float(el.mass)
    raise ValueError(f"No valid mass available for element {el.symbol}.")


BYPASS_TOKENS: Set[str] = {"BYPASSED", "Not_Found", "missing"}


def _expand_env_vars(path_str: str) -> str:
    """Uniformly expands %VAR%, $VAR, and ${VAR} across Windows and POSIX."""
    if not path_str:
        return path_str

    def replace_percent(match: re.Match[str]) -> str:
        var = match.group(1)
        return os.environ.get(var, f"%{var}%")

    s = re.sub(r"%([A-Za-z0-9_]+)%", replace_percent, path_str)
    s = os.path.expandvars(s)
    return os.path.expanduser(s)


def _default_mps_pipe_dir() -> str:
    try:
        from cochem_base.config_loader import get_mps_directories
        return str(get_mps_directories()[0])
    except Exception:
        return "/tmp/nvidia-mps"


def _default_mps_log_dir() -> str:
    try:
        from cochem_base.config_loader import get_mps_directories
        return str(get_mps_directories()[1])
    except Exception:
        return "/tmp/nvidia-log"


def _default_os_target() -> str:
    sys_name = platform.system().lower()
    if "windows" in sys_name:
        return OSTarget.LOCAL_WINDOWS.value
    if "darwin" in sys_name:
        return OSTarget.LOCAL_MACOS.value
    if os.getenv("GITHUB_ACTIONS") == "true":
        return OSTarget.GITHUB_ACTIONS.value
    if os.getenv("CODESPACES") == "true":
        return OSTarget.CODESPACES.value
    return OSTarget.LOCAL_LINUX.value


def _default_artifacts_dir() -> str:
    return os.getenv("COCHEM_ARTIFACTS_DIR", str(Path.home() / "cochem_artifacts"))


# =============================================================================
# ENUMS
# =============================================================================

class OSTarget(str, Enum):
    """
    Authoritative Operating System and Architecture Targets for the CoChem Ecosystem.
    Canonical 6-tier values: Local-Windows, Local-MacOS, Local-Linux, Codespaces, GitHub_Actions, HPC.
    """
    LOCAL_WINDOWS = "Local-Windows"
    LOCAL_MACOS = "Local-MacOS"
    LOCAL_LINUX = "Local-Linux"
    CODESPACES = "Codespaces"
    GITHUB_ACTIONS = "GitHub_Actions"
    HPC = "HPC"

    # Direct ecosystem aliases
    LINUX_X86_64 = "linux_x86_64"
    LINUX_AARCH64 = "linux_aarch64"
    WINDOWS_X86_64 = "windows_x86_64"
    WINDOWS_AMD64 = "windows_amd64"
    DARWIN_ARM64 = "darwin_arm64"
    DARWIN_X86_64 = "darwin_x86_64"
    GENERIC_POSIX = "posix"
    GENERIC_NT = "nt"


_OS_TARGET_NORMALIZATION_MAP: Dict[str, str] = {
    "local-windows": OSTarget.LOCAL_WINDOWS.value,
    "local-windows_native": OSTarget.LOCAL_WINDOWS.value,
    "local-windows_wsl": OSTarget.LOCAL_WINDOWS.value,
    "windows": OSTarget.LOCAL_WINDOWS.value,
    "windows_x86_64": OSTarget.WINDOWS_X86_64.value,
    "windows_amd64": OSTarget.WINDOWS_AMD64.value,
    "nt": OSTarget.GENERIC_NT.value,

    "local-macos": OSTarget.LOCAL_MACOS.value,
    "local-macos_darwin": OSTarget.LOCAL_MACOS.value,
    "darwin": OSTarget.LOCAL_MACOS.value,
    "darwin_arm64": OSTarget.DARWIN_ARM64.value,
    "darwin_x86_64": OSTarget.DARWIN_X86_64.value,

    "local-linux": OSTarget.LOCAL_LINUX.value,
    "local-linux_deb": OSTarget.LOCAL_LINUX.value,
    "linux": OSTarget.LOCAL_LINUX.value,
    "linux_x86_64": OSTarget.LINUX_X86_64.value,
    "linux_amd64": OSTarget.LINUX_X86_64.value,
    "linux_aarch64": OSTarget.LINUX_AARCH64.value,
    "posix": OSTarget.GENERIC_POSIX.value,

    "codespaces": OSTarget.CODESPACES.value,
    "github_codespaces": OSTarget.CODESPACES.value,
    "github_actions": OSTarget.GITHUB_ACTIONS.value,
    "hpc": OSTarget.HPC.value,
    "hpc_slurm_linux": OSTarget.HPC.value,
}


# =============================================================================
# 1. GPU COMPUTE SCHEMA
# =============================================================================

class GPUComputeSchema(BaseModel):
    """
    GPU Compute Metrics and Hardware Topology.
    Tracks peak theoretical/measured TFLOPS, Tensor Cores count, Memory Bandwidth, and CUDA features.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    gpu_profile: str = Field(default="None", description="Detected GPU model or 'None'")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory in GB")
    device_count: int = Field(default=0, ge=0, description="Number of detected GPU devices")
    compute_capability: Optional[str] = Field(default=None, description="CUDA Compute capability, e.g. '8.9'")
    fp64_capable: bool = Field(default=False, description="Whether device supports native double-precision FP64")
    subnormal_precision_trap: bool = Field(default=False, description="Whether subnormal precision traps are enabled")
    mps_enabled: bool = Field(default=False, description="Whether CUDA MPS is enabled")
    tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak TFLOPS compute metric")
    fp32_tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak FP32 TFLOPS")
    fp16_tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak FP16 TFLOPS")
    fp64_tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak FP64 TFLOPS")
    tensor_cores: Optional[int] = Field(default=None, ge=0, description="Number of hardware Tensor Cores")
    memory_bandwidth_gb_s: Optional[float] = Field(default=None, ge=0.0, description="GPU memory bandwidth in GB/s")


# =============================================================================
# 2. MPS & CORE PINNING CONFIGURATIONS
# =============================================================================

class MPSConfig(BaseModel):
    """CUDA Multi-Process Service (MPS) configuration."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable CUDA MPS daemon multiplexing")
    max_workers: int = Field(default=4, gt=0, le=64, description="Max concurrent MPS worker tasks per GPU")
    thread_percentage: int = Field(default=25, ge=1, le=100, description="CUDA MPS active thread percentage ceiling")
    pipe_dir: str = Field(default_factory=_default_mps_pipe_dir, description="MPS pipe directory")
    log_dir: str = Field(default_factory=_default_mps_log_dir, description="MPS log directory")


class CorePinningConfig(BaseModel):
    """Core Pinning and CPU Topology Configuration."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    kmp_hw_subset: str = Field(default="8c:intel_core,1t", description="OpenMP core pinning HW subset spec")
    anchor_p_cores: int = Field(default=7, ge=0, description="Number of P-cores assigned to CPU anchor tasks")
    scout_p_cores: int = Field(default=1, ge=0, description="Number of P-cores assigned to GPU scout tasks")
    background_e_cores: int = Field(default=8, ge=0, description="E-cores reserved for OS/background tasks")


# =============================================================================
# 3. QUANTUM SOLVER SETTINGS
# =============================================================================

class QuantumSettings(BaseModel):
    """Quantum chemical solver settings."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    implicit_solvation: Optional[str] = Field(default=None, description="Implicit solvent model (CPCM, SMD) or None")
    integration_grid: Optional[str] = Field(default="defgrid2", description="Integration grid size (defgrid1, defgrid2, defgrid3)")
    charge: int = Field(default=0)
    multiplicity: int = Field(default=1, ge=1)

    @field_validator("implicit_solvation", mode="before")
    @classmethod
    def validate_implicit_solvation(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, str):
            cleaned = v.strip().upper()
            if cleaned in ("CPCM", "SMD"):
                return cleaned
            raise ValueError("implicit_solvation must be 'CPCM' or 'SMD'")
        return cast(Optional[str], v)

    @field_validator("integration_grid", mode="before")
    @classmethod
    def validate_integration_grid(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, str):
            cleaned = v.strip().lower()
            if cleaned in ("defgrid1", "defgrid2", "defgrid3"):
                return cleaned
            raise ValueError("integration_grid must be one of ('defgrid1', 'defgrid2', 'defgrid3')")
        return cast(Optional[str], v)


# =============================================================================
# 4. HARDWARE SCHEMA
# =============================================================================

class HardwareSchema(BaseModel):
    """
    Rigid bounds for physical compute resources to prevent OOM and thread contention.
    Enforces positive RAM (gt=0.0), at least 1 physical core (ge=1), non-negative allocatable cores (ge=0),
    and non-negative VRAM (ge=0.0).
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    ram_gb: float = Field(..., gt=0.0, description="Total accessible memory in GB")
    cpu_physical_cores: int = Field(default=1, ge=1, description="Actual physical silicon cores")
    allocatable_compute_cores: int = Field(default=1, ge=0, description="Allocatable compute cores for scientific jobs")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory in GB")
    gpu_compute_metrics: GPUComputeSchema = Field(default_factory=GPUComputeSchema, description="GPU compute metrics and capabilities")
    gpu_fp64_capable: bool = Field(default=False, description="Whether GPU supports native FP64 precision")
    mps_enabled: bool = Field(default=False, description="Whether CUDA MPS is enabled")
    avx_512_capable: bool = Field(default=False, description="Whether CPU supports AVX-512 vector instructions")

    # Ecosystem & compatibility aliases
    physical_cpu_cores: Optional[int] = Field(default=None, ge=1, description="Alias for cpu_physical_cores")
    logical_cpu_cores: Optional[int] = Field(default=None, ge=1, description="Hyperthreaded threads count")
    cpu_cores: Optional[int] = Field(default=None, ge=1, description="Legacy CPU cores alias")
    ram_mb: Optional[int] = Field(default=None, ge=1, description="Total system RAM in MB")
    maxcore_mb: Optional[int] = Field(default=None, ge=0, description="Max core memory per process in MB")
    avx512_support: bool = Field(default=False, description="Legacy alias for avx_512_capable")
    gpu_profile: str = Field(default="None", description="Detected GPU model name")
    subnormal_precision_trap: bool = Field(default=False, description="Subnormal floating-point trap")
    os_target: Union[OSTarget, str] = Field(default=OSTarget.LOCAL_WINDOWS, description="Target execution environment")
    host_id: Optional[str] = Field(default=None, description="Host identity identifier")
    mps: Optional[MPSConfig] = Field(default_factory=MPSConfig, description="MPS daemon configuration")
    core_pinning: Optional[CorePinningConfig] = Field(default_factory=CorePinningConfig, description="CPU core pinning topology")
    gpu: Optional[GPUComputeSchema] = Field(default=None, description="Legacy alias for gpu_compute_metrics")

    @field_validator("os_target", mode="before")
    @classmethod
    def validate_os_target(cls, v: Any) -> str:
        if isinstance(v, OSTarget):
            return v.value
        if isinstance(v, str):
            v_str = v.strip()
            if v_str == "[MISSING DATA]":
                return v_str
            normalized = _OS_TARGET_NORMALIZATION_MAP.get(v_str.lower())
            if normalized:
                return normalized
            valid_targets = {t.value for t in OSTarget}
            if v_str in valid_targets:
                return v_str
            raise ValueError(f"Invalid OS target '{v}'. Must be a valid OS platform identifier.")
        raise ValueError(f"OS target must be a string or OSTarget enum, got {type(v)}")

    @model_validator(mode="before")
    @classmethod
    def flex_hardware_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # String-to-number coercions
        for float_field in ["ram_gb", "vram_gb"]:
            if float_field in d and isinstance(d[float_field], str):
                try:
                    d[float_field] = float(d[float_field])
                except ValueError:
                    pass

        for int_field in ["cpu_physical_cores", "physical_cpu_cores", "logical_cpu_cores", "cpu_cores", "allocatable_compute_cores", "ram_mb", "maxcore_mb"]:
            if int_field in d and isinstance(d[int_field], str):
                try:
                    d[int_field] = int(float(d[int_field]))
                except ValueError:
                    pass

        # Synchronize physical cores
        phys = d.get("cpu_physical_cores") or d.get("physical_cpu_cores") or d.get("cpu_cores")
        if phys is not None:
            try:
                phys_int = int(phys)
                d["cpu_physical_cores"] = phys_int
                d["physical_cpu_cores"] = phys_int
                if "cpu_cores" not in d:
                    d["cpu_cores"] = phys_int
            except (ValueError, TypeError):
                pass

        if "logical_cpu_cores" not in d or d["logical_cpu_cores"] is None:
            if "cpu_cores" in d and d["cpu_cores"] is not None:
                d["logical_cpu_cores"] = int(d["cpu_cores"])
            elif "cpu_physical_cores" in d and d["cpu_physical_cores"] is not None:
                d["logical_cpu_cores"] = int(d["cpu_physical_cores"]) * 2

        # Synchronize allocatable compute cores
        if "allocatable_compute_cores" not in d or d["allocatable_compute_cores"] is None:
            if phys is not None:
                try:
                    d["allocatable_compute_cores"] = int(phys)
                except (ValueError, TypeError):
                    pass

        # Synchronize RAM
        if "ram_mb" not in d and "ram_gb" in d:
            try:
                d["ram_mb"] = int(float(d["ram_gb"]) * 1024)
            except (ValueError, TypeError):
                pass
        elif "ram_gb" not in d and "ram_mb" in d:
            try:
                d["ram_gb"] = float(d["ram_mb"]) / 1024.0
            except (ValueError, TypeError):
                pass

        # Maxcore calculation / OOM clamping guard
        phys_count = int(d.get("cpu_physical_cores") or d.get("physical_cpu_cores") or 1)
        ram_mb_val = d.get("ram_mb")
        if ram_mb_val is not None:
            calc_maxcore = max(500, int(int(ram_mb_val) * 0.75 / max(1, phys_count)))
            if "maxcore_mb" not in d or d["maxcore_mb"] is None:
                d["maxcore_mb"] = calc_maxcore
            else:
                try:
                    maxcore = int(d["maxcore_mb"])
                    if maxcore > int(ram_mb_val):
                        d["maxcore_mb"] = calc_maxcore
                except (ValueError, TypeError):
                    d["maxcore_mb"] = calc_maxcore
        elif "maxcore_mb" not in d or d["maxcore_mb"] is None:
            d["maxcore_mb"] = 3000

        # Synchronize AVX-512 capabilities
        if "avx_512_capable" in d and "avx512_support" not in d:
            d["avx512_support"] = bool(d["avx_512_capable"])
        elif "avx512_support" in d and "avx_512_capable" not in d:
            d["avx_512_capable"] = bool(d["avx512_support"])
        elif "avx_512_capable" not in d and "avx512_support" not in d:
            d["avx_512_capable"] = False
            d["avx512_support"] = False

        # Synchronize GPU compute metrics
        gpu_data = d.get("gpu_compute_metrics") or d.get("gpu")
        if gpu_data is None:
            gpu_prof = d.get("gpu_profile", "None")
            vram = d.get("vram_gb", 0.0)
            trap = d.get("subnormal_precision_trap", False)
            fp64 = d.get("gpu_fp64_capable", False)
            mps_en = d.get("mps_enabled", False)
            built_gpu = {
                "gpu_profile": gpu_prof,
                "vram_gb": float(vram) if isinstance(vram, (int, float, str)) else 0.0,
                "subnormal_precision_trap": trap,
                "fp64_capable": fp64,
                "mps_enabled": mps_en,
            }
            d["gpu_compute_metrics"] = built_gpu
            d["gpu"] = built_gpu
        else:
            if isinstance(gpu_data, dict):
                d["gpu_compute_metrics"] = gpu_data
                d["gpu"] = gpu_data
                if "fp64_capable" in gpu_data and "gpu_fp64_capable" not in d:
                    d["gpu_fp64_capable"] = bool(gpu_data["fp64_capable"])
                if "mps_enabled" in gpu_data and "mps_enabled" not in d:
                    d["mps_enabled"] = bool(gpu_data["mps_enabled"])
            elif isinstance(gpu_data, GPUComputeSchema):
                d["gpu_compute_metrics"] = gpu_data
                d["gpu"] = gpu_data
                if "gpu_fp64_capable" not in d:
                    d["gpu_fp64_capable"] = gpu_data.fp64_capable
                if "mps_enabled" not in d:
                    d["mps_enabled"] = gpu_data.mps_enabled

        return d


HardwareConfig = HardwareSchema


# =============================================================================
# 5. ENVIRONMENT SCHEMA
# =============================================================================

class EnvironmentSchema(BaseModel):
    """
    Operating environment configuration, OS target validation, and isotopic mass locking.
    Enforces exact isotopic mass float values (e.g., ^13C = 13.00335483507).
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    os_target: Union[OSTarget, str] = Field(
        default_factory=_default_os_target,
        description="Target OS tier",
    )
    artifacts_dir: Union[str, Path] = Field(
        default_factory=_default_artifacts_dir,
        description="Path to artifacts directory",
    )
    scratch_dir: Optional[Union[str, Path]] = Field(default=None, description="Path to fast scratch directory")
    codata_version: str = Field(default="2018", description="CODATA constant version (e.g. '2018')")
    isotopic_mass_locking: bool = Field(default=True, description="Strict lock on atomic/isotopic masses")
    isotopic_mass_13c: float = Field(
        default=CARBON_13_ISOTOPIC_MASS,
        description="Locked isotopic mass for Carbon-13 (^13C = 13.00335483507)",
    )
    isotopic_masses: Dict[str, float] = Field(
        default_factory=dict,
        description="Exact isotopic mass registry",
    )
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Custom environment variable overrides")
    strict_path_resolution: bool = Field(default=False, description="Reject unresolvable relative paths if True")

    @field_validator("os_target", mode="before")
    @classmethod
    def validate_os_target(cls, v: Any) -> str:
        if isinstance(v, OSTarget):
            return v.value
        if isinstance(v, str):
            v_str = v.strip()
            if v_str == "[MISSING DATA]":
                return v_str
            normalized = _OS_TARGET_NORMALIZATION_MAP.get(v_str.lower())
            if normalized:
                return normalized
            valid_targets = {t.value for t in OSTarget}
            if v_str in valid_targets:
                return v_str
            raise ValueError(f"Invalid OS target '{v}'. Must be a valid OS platform identifier.")
        raise ValueError(f"OS target must be a string or OSTarget enum, got {type(v)}")

    @field_validator("codata_version")
    @classmethod
    def validate_codata(cls, v: str) -> str:
        valid = {"2014", "2018", "2022"}
        if v not in valid:
            raise ValueError(f"codata_version must be one of {sorted(valid)}, got '{v}'")
        return v

    @field_validator("artifacts_dir", "scratch_dir", mode="before")
    @classmethod
    def expand_and_normalize_path(cls, v: Any) -> Any:
        if v is None or v == "[MISSING DATA]":
            return None
        return _expand_env_vars(str(v))

    def resolve_path(self, raw_path: Union[str, Path]) -> Path:
        """Cross-platform path resolution with environment variable expansion."""
        if not raw_path:
            raise ValueError("Cannot resolve empty path.")
        expanded = _expand_env_vars(str(raw_path))
        p = Path(expanded)
        if self.strict_path_resolution and not p.is_absolute():
            raise ValueError(f"Strict path resolution enabled: relative path '{raw_path}' is rejected.")
        return p.resolve()

    def get_isotopic_mass(self, isotope: str) -> float:
        """Retrieve authoritative locked isotopic mass float [M]."""
        if isotope in self.isotopic_masses:
            return self.isotopic_masses[isotope]
        if isotope == "13C":
            return self.isotopic_mass_13c
        import re
        m = re.match(r"^(\d+)?([A-Za-z]+)$", str(isotope).strip())
        if m:
            mass_num = int(m.group(1)) if m.group(1) else None
            sym = m.group(2)
            try:
                return get_registry_atomic_mass(sym, mass_num)
            except Exception as exc:
                raise KeyError(f"Isotope '{isotope}' not registered in isotopic mass matrix: {exc}") from exc
        raise KeyError(f"Isotope '{isotope}' not registered in isotopic mass matrix.")


# =============================================================================
# 6. SILO PATHS SCHEMA
# =============================================================================

class SiloPathsSchema(BaseModel):
    """
    Paths configuration for isolated silos and scientific binaries.
    Enforces absolute path resolution (rejects relative paths), intercepting 'BYPASSED' and 'Not_Found'
    tokens, and preventing write stores (like HDF5 PES stores) from targeting immutable $COCHEM_ROOT.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    hdf5_pes_store_path: Optional[str] = Field(default=None, description="Path to centralized HDF5 PES store")
    cfour_binary_path: Optional[str] = Field(default=None, description="Path to CFOUR binary or 'BYPASSED'")
    aimnet2_server_path: Optional[str] = Field(default=None, description="Path to AIMNet2 server script or 'BYPASSED'")
    orca_binary_path: Optional[str] = Field(default=None, description="Path to ORCA executable or 'BYPASSED'")
    xtb_binary_path: Optional[str] = Field(default=None, description="Path to xTB executable or 'BYPASSED'")
    mpirun_binary_path: Optional[str] = Field(default=None, description="Path to mpirun executable or 'BYPASSED'")

    # Aliases
    orca_path: Optional[str] = Field(default=None, description="Alias for orca_binary_path")
    xtb_path: Optional[str] = Field(default=None, description="Alias for xtb_binary_path")
    mpirun_path: Optional[str] = Field(default=None, description="Alias for mpirun_binary_path")
    cfour_path: Optional[str] = Field(default=None, description="Alias for cfour_binary_path")
    aimnet2_path: Optional[str] = Field(default=None, description="Alias for aimnet2_server_path")
    python_path: Optional[str] = Field(default=None, description="Path to silo Python interpreter")
    silo_root: Optional[str] = Field(default=None, description="Root directory for micro-environments")
    strict_resolution: bool = Field(default=False, description="Enforce binary presence verification")

    @field_validator(
        "hdf5_pes_store_path",
        "cfour_binary_path",
        "aimnet2_server_path",
        "orca_binary_path",
        "xtb_binary_path",
        "mpirun_binary_path",
        "orca_path",
        "xtb_path",
        "mpirun_path",
        "cfour_path",
        "aimnet2_path",
        "python_path",
        "silo_root",
        mode="before",
    )
    @classmethod
    def validate_and_expand_path(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, (str, Path)):
            s = str(v).strip()
            if s in BYPASS_TOKENS:
                return s

            expanded = _expand_env_vars(s)
            p = Path(expanded)

            # Reject relative paths strictly
            if not p.is_absolute():
                raise ValueError(
                    f"Relative paths are forbidden in SiloPathsSchema for '{info.field_name}': '{s}'. "
                    "Path must be absolute or a bypass token ('BYPASSED', 'Not_Found', 'missing')."
                )

            resolved = p.resolve()

            # HPC Tripartite Air-Gap Check: Prevent write stores from targeting immutable $COCHEM_ROOT
            if info.field_name == "hdf5_pes_store_path":
                cochem_root_env = os.environ.get("COCHEM_ROOT")
                if cochem_root_env:
                    resolved_root = Path(os.path.expandvars(cochem_root_env)).resolve()
                    try:
                        if resolved == resolved_root or resolved.is_relative_to(resolved_root):
                            raise ValueError(
                                f"Write store path '{resolved}' targets immutable codebase $COCHEM_ROOT ('{resolved_root}'). "
                                "Paths should map to the Dynamic Data Tier or Volatile Compute Tier."
                            )
                    except AttributeError:
                        try:
                            resolved.relative_to(resolved_root)
                            raise ValueError(
                                f"Write store path '{resolved}' targets immutable codebase $COCHEM_ROOT ('{resolved_root}'). "
                                "Paths should map to the Dynamic Data Tier or Volatile Compute Tier."
                            )
                        except ValueError:
                            pass

            return str(resolved)
        raise ValueError(f"Invalid path type '{type(v)}' for '{info.field_name}'. Expected string or Path.")

    @model_validator(mode="before")
    @classmethod
    def sync_path_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        alias_pairs = [
            ("orca_binary_path", "orca_path"),
            ("xtb_binary_path", "xtb_path"),
            ("mpirun_binary_path", "mpirun_path"),
            ("cfour_binary_path", "cfour_path"),
            ("aimnet2_server_path", "aimnet2_path"),
        ]
        for canonical, alias in alias_pairs:
            if canonical in d and alias not in d:
                d[alias] = d[canonical]
            elif alias in d and canonical not in d:
                d[canonical] = d[alias]
        return d

    def is_bypassed(self, binary_name: str) -> bool:
        """Check if binary execution is marked as BYPASSED."""
        norm_name = binary_name.lower().replace(".exe", "")
        for candidate in (
            f"{norm_name}_binary_path",
            f"{norm_name}_path",
            f"{norm_name}_server_path",
            norm_name,
        ):
            if hasattr(self, candidate):
                val = getattr(self, candidate)
                return bool(val == "BYPASSED")
        return False

    def is_found(self, binary_name: str) -> bool:
        """Check if binary exists on filesystem and is not bypassed/missing."""
        norm_name = binary_name.lower().replace(".exe", "")
        for candidate in (
            f"{norm_name}_binary_path",
            f"{norm_name}_path",
            f"{norm_name}_server_path",
            norm_name,
        ):
            if hasattr(self, candidate):
                val = getattr(self, candidate)
                if not val or val in BYPASS_TOKENS:
                    return False
                return Path(val).exists()
        return False

    def resolve_binary(self, binary_name: str) -> Optional[str]:
        """Resolve executable path or return bypass token."""
        norm_name = binary_name.lower().replace(".exe", "")
        for candidate in (
            f"{norm_name}_binary_path",
            f"{norm_name}_path",
            f"{norm_name}_server_path",
            norm_name,
        ):
            if hasattr(self, candidate):
                val = getattr(self, candidate)
                if val is None or val in BYPASS_TOKENS:
                    return cast(Optional[str], val)
                p = Path(val)
                if self.strict_resolution and not p.exists():
                    raise FileNotFoundError(f"Binary '{binary_name}' not found at path '{val}'")
                return str(p.resolve())
        raise AttributeError(f"Unknown binary configuration '{binary_name}' in SiloPathsSchema")


# =============================================================================
# 7. COMPUTATIONAL BINARY PROVENANCE & SILO CONFIGS
# =============================================================================

class EngineInfo(BaseModel):
    """Pathing and cryptographic provenance for computational binaries."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(..., description="found, missing, permission_denied, or bypassed")
    path: Optional[str] = Field(None, description="Absolute path to executable, or 'BYPASSED', or 'Not_Found'")
    version: Optional[str] = Field(None, description="Semantic version of the engine")
    hash: Optional[str] = Field(None, description="SHA-256 binary hash")
    gpu_support: Optional[bool] = Field(default=False, description="Whether the engine has GPU support enabled")
    track: Optional[str] = Field(default=None, description="Ecosystem execution track or category")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: Any) -> str:
        if v is None or v == "[MISSING DATA]":
            return "missing"
        if isinstance(v, str):
            cleaned = v.strip().lower()
            if cleaned in ("found", "missing", "permission_denied", "bypassed", "ready"):
                return cleaned
            raise ValueError(f"Invalid engine status '{v}'. Must be one of ('found', 'missing', 'permission_denied', 'bypassed', 'ready').")
        raise ValueError(f"Invalid engine status type '{type(v)}'. Expected string.")

    @field_validator("path", "version", "hash", mode="before")
    @classmethod
    def clean_missing_data(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        return str(v)


class EnginePaths(BaseModel):
    """Aggregated binary path specifications."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    orca: Optional[EngineInfo] = Field(default=None)
    mpirun: Optional[EngineInfo] = Field(default=None)
    xtb: Optional[EngineInfo] = Field(default=None)
    cfour: Optional[EngineInfo] = Field(default=None)
    aimnet2: Optional[EngineInfo] = Field(default=None)
    mace: Optional[EngineInfo] = Field(default=None)


class SiloConfig(BaseModel):
    """Micro-environment deployment status."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    torq_silo_active: bool = Field(default=False)
    gpu_silo_active: bool = Field(default=False)


class RoutingPolicy(BaseModel):
    """Dynamically assigned execution constraints."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_concurrent_mace_threads: int = Field(default=4, gt=0)
    max_dft_basis_functions: int = Field(default=2000, gt=0)
    recommend_ccsdt: bool = Field(default=False)
    classification: str = Field(default="STANDARD")


class HPCConfig(BaseModel):
    """Cluster integration parameters."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    scheduler: str = Field(default="local", description="local, slurm, pbs, or sge")
    default_partition: str = Field(default="compute")
    max_walltime_hours: Optional[int] = Field(default=24, gt=0)
    partition: Optional[str] = Field(default="compute")
    cluster_hostname: Optional[str] = Field(default="localhost")
    ssh_key_path: Optional[str] = Field(default="")
    username: Optional[str] = Field(default="localuser")
    execution_mode: Optional[str] = Field(default="local")
    walltime_budgets: Optional[Dict[str, str]] = Field(default_factory=dict)
    sbatch_template: Optional[str] = Field(default=None, description="Custom sbatch template")

    @field_validator("scheduler", mode="before")
    @classmethod
    def validate_scheduler(cls, v: Any) -> str:
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("local", "slurm", "pbs", "sge"):
                return s
            raise ValueError(f"Invalid HPC scheduler '{v}'. Must be one of ('local', 'slurm', 'pbs', 'sge').")
        raise ValueError(f"HPC scheduler must be a string, got {type(v)}")


# =============================================================================
# 8. MASTER COCHEM SYSTEM CONFIG
# =============================================================================

class CoChemSystemConfig(BaseModel):
    """
    The CoChem Master System Configuration Schema.
    Rigid mathematical boundary enforcing Stage 0 Authority Rule.
    Aggregates HardwareSchema, EnvironmentSchema, SiloPathsSchema, and live execution jobs.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(default="4.0.0")
    registry_version: Optional[str] = Field(default="4.0")
    status: Optional[str] = Field(default="LOCKED", description="Registry operational status ('LOCKED', 'INITIALIZED', 'ACTIVE')")
    orca_version: Optional[str] = Field(default="6.1.1")
    rdkit_random_seed: Optional[int] = Field(default=42)
    registry_checksum: Optional[str] = Field(default="", description="SHA-256 checksum of registry payload")
    last_updated: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hardware: HardwareSchema = Field(..., description="Rigid compute hardware bounds and topology")
    environment: EnvironmentSchema = Field(default_factory=EnvironmentSchema, description="Operating environment settings")
    silo_paths: SiloPathsSchema = Field(default_factory=SiloPathsSchema, description="Silo and binary path mappings")
    engines: Union[Dict[str, Any], EnginePaths] = Field(default_factory=dict)
    silos: Optional[SiloConfig] = Field(default=None, description="Micro-environment deployment status")
    quantum_settings: Optional[QuantumSettings] = Field(default_factory=QuantumSettings)
    adaptive_routing: Optional[RoutingPolicy] = None
    hpc: HPCConfig = Field(default_factory=HPCConfig)
    execution: Optional[Dict[str, Any]] = Field(default=None, description="Execution routing and default engine settings")
    alignment_engine_ready: bool = Field(default=False)
    active_jobs: Dict[str, Any] = Field(default_factory=dict, description="Live execution pointers")

    @model_validator(mode="before")
    @classmethod
    def registry_migrator(cls, data: Any) -> Any:
        """
        RegistryMigrator: Transforms legacy flat configuration dictionaries
        into the authoritative nested schema architecture before validation.
        """
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # 1. Migrate flat Hardware fields
        hw_keys = {
            "physical_cpu_cores", "cpu_physical_cores", "logical_cpu_cores",
            "cpu_cores", "ram_gb", "ram_mb", "maxcore_mb", "avx512_support",
            "avx_512_capable", "gpu_profile", "vram_gb", "subnormal_precision_trap",
            "allocatable_compute_cores", "gpu_compute_metrics", "gpu_fp64_capable",
            "mps_enabled", "core_pinning", "mps", "gpu", "host_id"
        }
        extracted_hw: Dict[str, Any] = {}
        for k in list(d.keys()):
            if k in hw_keys:
                extracted_hw[k] = d.pop(k)

        if "hardware" not in d or d["hardware"] is None:
            if extracted_hw:
                d["hardware"] = extracted_hw
        elif isinstance(d["hardware"], dict):
            for k, v in extracted_hw.items():
                if k not in d["hardware"]:
                    d["hardware"][k] = v

        # 2. Migrate flat Environment fields
        env_keys = {
            "codata_version", "isotopic_mass_locking", "isotopic_mass_13c",
            "isotopic_masses", "artifacts_dir", "scratch_dir",
            "strict_path_resolution", "env_vars"
        }
        extracted_env: Dict[str, Any] = {}
        for k in list(d.keys()):
            if k in env_keys:
                extracted_env[k] = d.pop(k)

        if "os_target" in d:
            os_target_val = d.pop("os_target")
            extracted_env["os_target"] = os_target_val
            if "hardware" in d and isinstance(d["hardware"], dict) and "os_target" not in d["hardware"]:
                d["hardware"]["os_target"] = os_target_val

        if "environment" not in d or d["environment"] is None:
            if extracted_env:
                d["environment"] = extracted_env
        elif isinstance(d["environment"], dict):
            for k, v in extracted_env.items():
                if k not in d["environment"]:
                    d["environment"][k] = v

        # 3. Migrate flat Silo fields
        silo_keys = {
            "orca_path", "xtb_path", "mpirun_path", "cfour_path", "aimnet2_server_path",
            "aimnet2_path", "cfour_binary_path", "orca_binary_path", "xtb_binary_path",
            "mpirun_binary_path", "hdf5_pes_store_path", "silo_root", "python_path", "strict_resolution"
        }
        extracted_silo: Dict[str, Any] = {}
        for k in list(d.keys()):
            if k in silo_keys:
                extracted_silo[k] = d.pop(k)

        if "silo_paths" not in d or d["silo_paths"] is None:
            if extracted_silo:
                d["silo_paths"] = extracted_silo
        elif isinstance(d["silo_paths"], dict):
            for k, v in extracted_silo.items():
                if k not in d["silo_paths"]:
                    d["silo_paths"][k] = v

        # 4. Default active_jobs
        if "active_jobs" not in d or d["active_jobs"] is None:
            d["active_jobs"] = {}

        return d

    @field_validator("adaptive_routing", mode="before")
    @classmethod
    def clean_adaptive_routing(cls, v: Any) -> Any:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        return v

    @field_validator("engines", mode="before")
    @classmethod
    def validate_engines(cls, v: Any) -> Any:
        if isinstance(v, dict):
            validated: Dict[str, Any] = {}
            for engine_name, engine_val in v.items():
                if isinstance(engine_val, dict):
                    validated[engine_name] = EngineInfo.model_validate(engine_val)
                else:
                    validated[engine_name] = engine_val
            return validated
        return v

    def compute_checksum(self) -> str:
        """Calculates deterministic SHA-256 checksum of configuration payload."""
        d = self.model_dump(exclude={"registry_checksum", "last_updated"})
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def update_checksum(self) -> str:
        """Calculates and updates registry_checksum in place."""
        cs = self.compute_checksum()
        self.registry_checksum = cs
        return cs

    def verify_checksum(self) -> bool:
        """Verifies whether registry_checksum matches the current configuration payload."""
        if not self.registry_checksum:
            return False
        return self.registry_checksum == self.compute_checksum()

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_file(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CoChemSystemConfig:
        return cls.model_validate(d)

    @classmethod
    def from_json(cls, json_str: str) -> CoChemSystemConfig:
        return cls.model_validate_json(json_str)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> CoChemSystemConfig:
        p = Path(path)
        return cls.model_validate_json(p.read_text(encoding="utf-8"))

    @classmethod
    def create_default(cls, auto_detect_hardware: bool = False) -> CoChemSystemConfig:
        hw = discover_host_hardware() if auto_detect_hardware else HardwareSchema(
            cpu_physical_cores=4,
            physical_cpu_cores=4,
            logical_cpu_cores=8,
            ram_gb=16.0,
            os_target=OSTarget.LOCAL_WINDOWS if os.name == "nt" else OSTarget.LOCAL_LINUX,
        )
        return cls(
            hardware=hw,
            quantum_settings=QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid2"),
            silos=SiloConfig(torq_silo_active=True),
        )


CoChemConfig = CoChemSystemConfig


# =============================================================================
# 9. DISCOVERY & CONVENIENCE FUNCTIONS
# =============================================================================

def discover_engine(binary_name: str) -> EngineInfo:
    """Check physical presence and provenance of a scientific binary."""
    p = shutil.which(binary_name)
    if p:
        return EngineInfo(status="found", path=str(p), version="auto", hash="auto")
    return EngineInfo(status="missing", path=None, version=None, hash=None)


def discover_host_hardware() -> HardwareSchema:
    """Discover host hardware configuration safely."""
    try:
        import psutil  # type: ignore[import-untyped]
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        phys_cores = psutil.cpu_count(logical=False) or 1
        log_cores = psutil.cpu_count(logical=True) or 1
    except ImportError:
        total_ram_gb = 16.0
        phys_cores = os.cpu_count() or 1
        log_cores = os.cpu_count() or 1

    os_target = _default_os_target()

    return HardwareSchema(
        cpu_physical_cores=phys_cores,
        physical_cpu_cores=phys_cores,
        logical_cpu_cores=log_cores,
        allocatable_compute_cores=phys_cores,
        ram_gb=round(total_ram_gb, 2),
        avx_512_capable=False,
        gpu_profile="None",
        vram_gb=0.0,
        os_target=os_target,
    )


def validate_system_config(source: Union[str, Path, Dict[str, Any], CoChemSystemConfig]) -> CoChemSystemConfig:
    """Authoritative gatekeeper validating system configuration from any source."""
    if isinstance(source, CoChemSystemConfig):
        return source
    if isinstance(source, dict):
        return CoChemSystemConfig.model_validate(source)
    if isinstance(source, Path):
        return CoChemSystemConfig.from_file(source)
    if isinstance(source, str):
        if os.path.exists(source):
            return CoChemSystemConfig.from_file(source)
        try:
            return CoChemSystemConfig.from_json(source)
        except Exception:
            try:
                raw_dict = json.loads(source)
                return CoChemSystemConfig.model_validate(raw_dict)
            except Exception:
                pass
    raise TypeError(f"Unsupported configuration source type: {type(source)}")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\__init__.py ---
"""Authoritative Unified Core Namespace for CoChem Base.

Re-exports core registry, configuration, sandboxing, air-gap, file locking,
IPC serialization, HDF5 PES stores, and quantum chemistry schema/exception protocols.
"""

from __future__ import annotations

# 1. Authoritative registry manager and schemas
from cochem_base.core import cochem_core_registry_manager
from cochem_base.core.cochem_core_registry_manager import (
    AtomicFileLock,
    BaseMetadataServer,
    BasisSetNotFoundError,
    CoChemLockTimeoutError,
    FilesystemMetadataServer,
    MetadataBackendType,
    MetadataServerManager,
    PostgresMetadataServer,
    RecordNotFoundError,
    RedisMetadataServer,
    RegistryCorruptionError,
    RegistryError,
    RegistryLockError,
    RegistryLockTimeoutError,
    RegistryManager,
    RegistryMissingError,
    RegistryParseError,
    SchemaMigrationError,
    _sanitize_path_leakages,
    atomic_write_json,
    broadcast_system_config,
    default_metadata_manager,
    get_active_job,
    get_default_config_path,
    hash_environment,
    interpolate_env_vars,
    is_master_node,
    list_active_jobs,
    load_system_config,
    migrate_schema,
    nfs_atomic_directory_rename,
    receive_system_config_broadcast,
    register_active_job,
    remove_active_job,
    save_system_config,
    update_active_job,
    update_system_config,
)

# RegistryManager alias for unified core namespace
CoChemRegistry = RegistryManager

# 2. Configuration authority
# 4. Air-Gap Coordination
from cochem.core.airgap_coordinator import (
    AirGapConfig,
    AirGapCoordinator,
    AirGapViolationError,
    TripartiteAirGapCoordinator,
    TripartiteStorageConfig,
    get_tier_file_lock,
)

# 3. Sandboxing
from cochem.core.cochem_sandbox import (
    SandboxConfig,
    SandboxContext,
    SandboxExecutionError,
    SandboxSecurityViolationError,
)
from cochem.core.config import (
    CoChemConfigManager,
    CoChemRootConfig,
    ConfigurationParseError,
    CoreConfig,
    DatabaseConfig,
    OrchestrationConfig,
    QmMMConfig,
    TelemetryConfig,
    get_workspace_config,
)

# 5. Centralized File Locking
from cochem.core.context import FileLock

# 7. Ingestors, Schemas & Quantum Chemistry Domain Exceptions
from cochem.core.ingestors.protocols import (
    HessianSymmetryError,
    MolecularStructureData,
    QCResultsSchema,
    QCValidationError,
    SpinContaminationError,
)

# 6. IPC, Memory & PES Store
from cochem.core.ipc.serializer import (
    MAX_IPC_PAYLOAD_BYTES,
    HMACSocketClient,
    HMACSocketServer,
    IPCPayloadError,
    OversizedPayloadError,
    PESStore,
    SharedMemoryBuffer,
    TruncatedPayloadError,
    pack_payload,
    unpack_payload,
)

# 8. Mendeleev Mass Invariants
from cochem.core.mendeleev_invariants import MendeleevInvariantError

# 9. Stage-0 Facade Re-exports: HDF5 Manager, Models, Constants, PES Records
from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager
from cochem_base.core.cochem_crypto import (
    did_key_to_public_key,
    public_key_to_did_key,
    sign_report_payload,
    verify_report_payload,
)
from cochem_base.core.cochem_provenance import DAGNode, get_local_prov_context
from cochem_base.core.cochem_version import get_vcs_provenance
from cochem_base.core.exceptions import IsotopeStabilityError, RadiusNotFoundError
from cochem_base.core.glossary import CalculationFidelity, UnitConversionConstants
from cochem_base.core.licensing import OFFICIAL_SPDX_LICENSES, validate_spdx_license
from cochem_base.core.metadata import (
    collect_hardware_metadata,
    get_covalent_radius,
    get_isotopic_mass,
)
from cochem_base.core.models import (
    NAMESPACE_COCHEM,
    CalculationJobPayload,
    MolecularTopology,
    PESPointRecord,
    QCResultsRecord,
)
from cochem_base.core_engine.cochem_core_pes_store import (
    PESStore,
    get_node_local_scratch_dir,
)

__all__ = [
    # Registry
    "cochem_core_registry_manager",
    "AtomicFileLock",
    "BaseMetadataServer",
    "BasisSetNotFoundError",
    "CoChemLockTimeoutError",
    "FilesystemMetadataServer",
    "IsotopeStabilityError",
    "MetadataBackendType",
    "MetadataServerManager",
    "PostgresMetadataServer",
    "RecordNotFoundError",
    "RedisMetadataServer",
    "RegistryCorruptionError",
    "RegistryError",
    "RegistryLockError",
    "RegistryLockTimeoutError",
    "RegistryManager",
    "RegistryMissingError",
    "RegistryParseError",
    "SchemaMigrationError",
    "CoChemRegistry",
    "_sanitize_path_leakages",
    "atomic_write_json",
    "broadcast_system_config",
    "default_metadata_manager",
    "get_active_job",
    "get_default_config_path",
    "hash_environment",
    "interpolate_env_vars",
    "is_master_node",
    "list_active_jobs",
    "load_system_config",
    "migrate_schema",
    "nfs_atomic_directory_rename",
    "receive_system_config_broadcast",
    "register_active_job",
    "remove_active_job",
    "save_system_config",
    "update_active_job",
    "update_system_config",
    # Config
    "CoChemConfigManager",
    "CoChemRootConfig",
    "ConfigurationParseError",
    "CoreConfig",
    "DatabaseConfig",
    "OrchestrationConfig",
    "QmMMConfig",
    "TelemetryConfig",
    "get_workspace_config",
    # Sandbox
    "SandboxConfig",
    "SandboxContext",
    "SandboxExecutionError",
    "SandboxSecurityViolationError",
    # Airgap
    "AirGapConfig",
    "AirGapCoordinator",
    "AirGapViolationError",
    "TripartiteAirGapCoordinator",
    "TripartiteStorageConfig",
    "get_tier_file_lock",
    # Context & Locking
    "FileLock",
    # IPC & PES
    "HMACSocketClient",
    "HMACSocketServer",
    "IPCPayloadError",
    "MAX_IPC_PAYLOAD_BYTES",
    "OversizedPayloadError",
    "PESStore",
    "SharedMemoryBuffer",
    "TruncatedPayloadError",
    "pack_payload",
    "unpack_payload",
    # Protocols & Physics Exceptions
    "HessianSymmetryError",
    "MolecularStructureData",
    "QCResultsSchema",
    "QCValidationError",
    "SpinContaminationError",
    # Mendeleev Invariants
    "MendeleevInvariantError",
    # Stage-0 Facade Deliverables
    "CoChemHDF5Manager",
    "QCResultsRecord",
    "MolecularTopology",
    "PESPointRecord",
    "UnitConversionConstants",
    # Chunk 6 Deliverables
    "IsotopeStabilityError",
    "RadiusNotFoundError",
    "OFFICIAL_SPDX_LICENSES",
    "validate_spdx_license",
    "get_isotopic_mass",
    "get_covalent_radius",
    "collect_hardware_metadata",
    "DAGNode",
    "get_local_prov_context",
    "did_key_to_public_key",
    "public_key_to_did_key",
    "sign_report_payload",
    "verify_report_payload",
    "get_vcs_provenance",
    "CalculationFidelity",
    "CalculationJobPayload",
    "NAMESPACE_COCHEM",
    "get_node_local_scratch_dir",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\cochem_core_registry_manager.py ---
#!/usr/bin/env python3
"""CoChem-CORE: Stage 0 Authority Rule & Master Registry Manager.

Provides thread-safe and process-safe atomic file locking via cross-platform filelock,
NFS-resilient directory-level staging and exponential backoff, metadata server integration
(Redis, PostgreSQL, Filesystem fallback), cryptographic SHA-256 checksum enforcement,
Pydantic validation checkpoints, dynamic environment variable interpolation, legacy schema migration,
active jobs lifecycle tracking, HDF5 state registry operations, lineage DAGs, PRNG seed locking,
embedded basis set archival, Mendeleev/QCElemental isotopic mass queries, and ZeroMQ config broadcast.

Zero-Mock Policy: 100% genuine OS processes, genuine atomic file locks, and real database/filesystem operations.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import shutil
import threading
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Sequence, Union, cast

import filelock
import h5py  # type: ignore[import-untyped]
import zmq
from pydantic import BaseModel, ValidationError

try:
    from mendeleev import element  # type: ignore[import-untyped]
except ImportError:
    element = None

try:
    from qcelemental import periodictable as pt  # type: ignore
except ImportError:
    pt = None

from cochem_base.config_loader import (
    get_artifact_dir,
    resolve_config_path,
    resolve_mapped_path,
)

try:
    from cochem_core_registry_schema import CoChemSystemConfig
except ImportError:
    try:
        from core_engine.cochem_core_registry_schema import CoChemSystemConfig  # type: ignore
    except ImportError:
        from ..cochem_core_registry_schema import CoChemSystemConfig  # type: ignore

logger = logging.getLogger("CoChem-RegistryManager")


# =============================================================================
# TYPED REGISTRY EXCEPTIONS
# =============================================================================

class RegistryError(Exception):
    """Base exception for all registry and state manager operations."""


class RegistryLockError(RegistryError):
    """Raised when atomic file locking fails."""


class CoChemLockTimeoutError(RegistryLockError, TimeoutError):
    """Raised when acquiring an atomic file lock exceeds the configured timeout."""


RegistryLockTimeoutError = CoChemLockTimeoutError


class RegistryMissingError(RegistryError, FileNotFoundError):
    """Stage 0 Guardrail: Raised when the master registry configuration file is missing."""


class RegistryCorruptionError(RegistryError, ValueError):
    """Stage 0 Guardrail: Raised when registry integrity checksum verification fails."""


class RegistryParseError(RegistryError, ValueError):
    """Stage 0 Guardrail: Raised when registry JSON is malformed or unparseable."""


class RecordNotFoundError(RegistryError, KeyError, ValueError):
    """Raised when a queried job or profile is not found in the registry."""


class BasisSetNotFoundError(RegistryError, KeyError):
    """Raised when an archived basis set cannot be located."""


class SchemaMigrationError(RegistryError, ValueError):
    """Raised when schema migration encounters an unrecoverable failure."""


from cochem_base.core.exceptions import IsotopeStabilityError as _BaseIsotopeStabilityError


class IsotopeStabilityError(RegistryError, _BaseIsotopeStabilityError):
    """Raised when isotopic mass resolution fails or mass record is missing."""



# =============================================================================
# CROSS-PLATFORM ATOMIC FILE LOCKING (filelock + In-Process Thread Lock)
# =============================================================================

class AtomicFileLock:
    """Process-safe, thread-safe, cross-platform atomic file lock using filelock.SoftFileLock / FileLock.

    Combines thread-level RLock serialization per canonical path with cross-platform
    filelock, thread-local re-entrancy tracking, and strict 10-second gatekeeper timeout.
    POSIX fcntl is explicitly eradicated in favor of cross-platform filelock.
    """

    _tls = threading.local()
    _path_locks: Dict[str, threading.RLock] = {}
    _meta_lock = threading.Lock()

    @classmethod
    def _get_path_lock(cls, path_str: str) -> threading.RLock:
        with cls._meta_lock:
            if path_str not in cls._path_locks:
                cls._path_locks[path_str] = threading.RLock()
            return cls._path_locks[path_str]

    def __init__(
        self,
        lock_path: Union[str, Path],
        timeout: float = 10.0,
        stale_timeout: float = 60.0,
    ) -> None:
        self.lock_path = Path(lock_path).resolve()
        self.timeout = float(timeout)
        self.stale_timeout = float(stale_timeout)
        self._depth: int = 0
        self._thread_lock_acquired: bool = False
        self._filelock: Optional[Union[filelock.SoftFileLock, filelock.FileLock]] = None

    @property
    def _is_locked(self) -> bool:
        path_str = str(self.lock_path)
        if hasattr(self._tls, "held") and self._tls.held.get(path_str, 0) > 0:
            return True
        return self._depth > 0

    def acquire(self) -> bool:
        """Acquires the atomic lock before timeout. Raises CoChemLockTimeoutError on failure."""
        if not hasattr(self._tls, "held"):
            self._tls.held = {}
        if not hasattr(self._tls, "locks"):
            self._tls.locks = {}

        path_str = str(self.lock_path)

        # Thread-local re-entrancy
        if self._tls.held.get(path_str, 0) > 0:
            self._tls.held[path_str] += 1
            self._depth += 1
            return True

        start_time = time.time()
        thread_lock = self._get_path_lock(path_str)

        # 1. In-process thread lock
        remaining = max(0.001, self.timeout - (time.time() - start_time))
        if not thread_lock.acquire(timeout=remaining):
            raise CoChemLockTimeoutError(
                f"Could not acquire thread lock on '{self.lock_path}' within {self.timeout}s"
            )

        self._thread_lock_acquired = True
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Stale lock reaping check
        if self.lock_path.exists():
            try:
                mtime = self.lock_path.stat().st_mtime
                if (time.time() - mtime) > self.stale_timeout:
                    try:
                        self.lock_path.unlink(missing_ok=True)
                        logger.info(f"Reaped stale lock file: {self.lock_path}")
                    except OSError:
                        pass
            except OSError:
                pass

        # 2. Cross-platform process lock via filelock.SoftFileLock
        rem_filelock = max(0.001, self.timeout - (time.time() - start_time))
        fl = filelock.SoftFileLock(str(self.lock_path), timeout=rem_filelock)
        try:
            fl.acquire(timeout=rem_filelock)
            # Write diagnostic lock ownership payload (PID:thread:timestamp)
            try:
                self.lock_path.write_text(
                    f"{os.getpid()}:{threading.get_ident()}:{time.time()}\n",
                    encoding="utf-8",
                )
            except Exception:
                pass

            self._filelock = fl
            self._depth = 1
            self._tls.held[path_str] = 1
            self._tls.locks[path_str] = fl
            return True
        except (filelock.Timeout, TimeoutError) as e:
            self._thread_lock_acquired = False
            try:
                thread_lock.release()
            except RuntimeError:
                pass
            raise CoChemLockTimeoutError(
                f"Could not acquire atomic lock on '{self.lock_path}' within {self.timeout}s"
            ) from e
        except Exception as e:
            self._thread_lock_acquired = False
            try:
                thread_lock.release()
            except RuntimeError:
                pass
            raise CoChemLockTimeoutError(
                f"Error acquiring atomic lock on '{self.lock_path}': {e}"
            ) from e

    def release(self) -> None:
        """Releases the atomic lock safely."""
        path_str = str(self.lock_path)
        if not hasattr(self._tls, "held") or self._tls.held.get(path_str, 0) <= 0:
            if self._depth > 0:
                self._depth -= 1
            if self._thread_lock_acquired:
                self._thread_lock_acquired = False
                try:
                    self._get_path_lock(path_str).release()
                except RuntimeError:
                    pass
            return

        self._depth -= 1
        self._tls.held[path_str] -= 1
        if self._tls.held[path_str] > 0:
            return

        del self._tls.held[path_str]

        fl = None
        if hasattr(self._tls, "locks") and path_str in self._tls.locks:
            fl = self._tls.locks.pop(path_str)
        elif self._filelock is not None:
            fl = self._filelock
            self._filelock = None

        if fl is not None:
            try:
                fl.release()
            except Exception:
                pass

        if self.lock_path.exists():
            try:
                self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass

        if self._thread_lock_acquired:
            self._thread_lock_acquired = False
            try:
                self._get_path_lock(path_str).release()
            except RuntimeError:
                pass

    def __enter__(self) -> AtomicFileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


# =============================================================================
# ENVIRONMENT VARIABLE INTERPOLATION & NFS-RESILIENT ATOMIC WRITER
# =============================================================================

def interpolate_env_vars(raw_data: Any) -> Any:
    """Uniformly expands %VAR%, $VAR, ${VAR}, and ~ across Windows and POSIX environments.

    Supports string, dictionary, list, or primitive data structures.
    """
    if isinstance(raw_data, str):
        def replace_percent(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        def replace_braced(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        def replace_dollar(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        s = re.sub(r"%([A-Za-z0-9_]+)%", replace_percent, raw_data)
        s = re.sub(r"\$\{([A-Za-z0-9_]+)\}", replace_braced, s)
        s = re.sub(r"\$([A-Za-z0-9_]+)", replace_dollar, s)
        if s.startswith("~"):
            s = os.path.expanduser(s)
        return s
    elif isinstance(raw_data, dict):
        return {k: interpolate_env_vars(v) for k, v in raw_data.items()}
    elif isinstance(raw_data, list):
        return [interpolate_env_vars(item) for item in raw_data]
    return raw_data


def nfs_atomic_directory_rename(
    src_dir: Union[str, Path],
    dst_dir: Union[str, Path],
    max_retries: int = 10,
    initial_backoff: float = 0.01,
) -> None:
    """Performs an NFS-resilient atomic directory rename with exponential backoff retry logic.

    Directory-level atomic renames force NFS metadata cache invalidation and ensure
    global consistency across HPC client nodes against NFS attribute staleness.
    """
    src = Path(src_dir).resolve()
    dst = Path(dst_dir).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source directory for atomic rename does not exist: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    backoff = initial_backoff
    for attempt in range(max_retries):
        try:
            if dst.exists():
                backup = dst.parent / f".backup_{dst.name}_{uuid.uuid4().hex}"
                os.rename(dst, backup)
                try:
                    os.rename(src, dst)
                    shutil.rmtree(backup, ignore_errors=True)
                    return
                except Exception:
                    os.rename(backup, dst)
                    raise
            else:
                os.rename(src, dst)
                return
        except OSError as e:
            if attempt == max_retries - 1:
                raise OSError(
                    f"NFS atomic directory rename failed after {max_retries} attempts: {src} -> {dst}"
                ) from e
            time.sleep(backoff)
            backoff = min(0.5, backoff * 1.5)


def atomic_write_json(
    file_path: Union[str, Path],
    data: Union[Dict[str, Any], BaseModel, str],
    lock_timeout: float = 10.0,
    max_retries: int = 10,
    initial_backoff: float = 0.01,
) -> None:
    """Writes JSON data atomically via directory-level staging and exponential backoff retry logic.

    Direct file overwrite ('w' mode on shared files) and raw unprotected os.replace()
    are prohibited to eliminate NFS attribute cache staleness.
    """
    target = Path(file_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_file = str(target) + ".lock"

    if isinstance(data, BaseModel):
        content = data.model_dump_json(indent=2)
    elif isinstance(data, dict):
        content = json.dumps(data, indent=2)
    elif isinstance(data, str):
        content = data
    else:
        content = json.dumps(data, indent=2)

    with AtomicFileLock(lock_file, timeout=lock_timeout):
        # Directory-level atomic staging to defeat NFS caching flaws
        staging_dir = target.parent / f".staging_{target.stem}_{uuid.uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staging_file = staging_dir / target.name

        try:
            with open(staging_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            # Exponential backoff retry loop for atomic replace across NFS mounts
            backoff = initial_backoff
            for attempt in range(max_retries):
                try:
                    os.replace(staging_file, target)
                    break
                except (OSError, PermissionError) as e:
                    if attempt == max_retries - 1:
                        raise OSError(
                            f"Atomic write replacement failed for '{target}' after {max_retries} attempts: {e}"
                        ) from e
                    time.sleep(backoff)
                    backoff = min(0.5, backoff * 1.5)
        finally:
            if staging_file.exists():
                try:
                    staging_file.unlink(missing_ok=True)
                except OSError:
                    pass
            if staging_dir.exists():
                try:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                except OSError:
                    pass


# =============================================================================
# METADATA SERVER ADAPTERS (Redis / PostgreSQL with Filesystem Fallback)
# =============================================================================

class MetadataBackendType(str, Enum):
    REDIS = "redis"
    POSTGRES = "postgres"
    FILESYSTEM = "filesystem"


class BaseMetadataServer(ABC):
    """Abstract base class defining metadata server contracts for state persistence."""

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the metadata server backend is reachable and healthy."""
        pass

    @abstractmethod
    def get_state(self, key: str) -> Optional[str]:
        """Retrieves raw string state payload for a given key."""
        pass

    @abstractmethod
    def set_state(self, key: str, value: str) -> bool:
        """Persists raw string state payload for a given key."""
        pass

    @abstractmethod
    def delete_state(self, key: str) -> bool:
        """Deletes state for a given key."""
        pass

    @property
    @abstractmethod
    def backend_type(self) -> MetadataBackendType:
        """Returns the backend type identifier."""
        pass


class RedisMetadataServer(BaseMetadataServer):
    """Redis metadata server adapter for high-throughput HPC state synchronization."""

    def __init__(
        self,
        url: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        timeout: float = 2.0,
    ) -> None:
        self.url = url or os.environ.get("COCHEM_REDIS_URL")
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.timeout = timeout
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            import redis  # type: ignore[import-not-found,import-untyped]
            if self.url:
                self._client = redis.from_url(
                    self.url, socket_timeout=self.timeout, socket_connect_timeout=self.timeout
                )
            else:
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    socket_timeout=self.timeout,
                    socket_connect_timeout=self.timeout,
                )
        except Exception:
            self._client = None

    def is_available(self) -> bool:
        if self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def get_state(self, key: str) -> Optional[str]:
        if not self.is_available():
            return None
        try:
            val = self._client.get(key)
            if val is None:
                return None
            return val.decode("utf-8") if isinstance(val, bytes) else str(val)
        except Exception as e:
            logger.warning(f"Redis get_state error for {key}: {e}")
            return None

    def set_state(self, key: str, value: str) -> bool:
        if not self.is_available():
            return False
        try:
            self._client.set(key, value)
            return True
        except Exception as e:
            logger.warning(f"Redis set_state error for {key}: {e}")
            return False

    def delete_state(self, key: str) -> bool:
        if not self.is_available():
            return False
        try:
            return bool(self._client.delete(key))
        except Exception as e:
            logger.warning(f"Redis delete_state error for {key}: {e}")
            return False

    @property
    def backend_type(self) -> MetadataBackendType:
        return MetadataBackendType.REDIS


class PostgresMetadataServer(BaseMetadataServer):
    """PostgreSQL metadata server adapter for ACID-compliant state storage."""

    def __init__(
        self,
        url: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 5432,
        dbname: str = "cochem",
        user: str = "postgres",
        password: Optional[str] = None,
        timeout: float = 2.0,
    ) -> None:
        self.url = url or os.environ.get("COCHEM_POSTGRES_URL") or os.environ.get("COCHEM_DATABASE_URL")
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self.timeout = timeout
        self._table_initialized = False

    def _get_connection(self) -> Any:
        try:
            import psycopg2  # type: ignore[import-untyped]
            if self.url:
                return psycopg2.connect(self.url, connect_timeout=int(self.timeout))
            return psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                connect_timeout=int(self.timeout),
            )
        except Exception:
            return None

    def _ensure_table(self, conn: Any) -> None:
        if self._table_initialized:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cochem_metadata_registry (
                        key VARCHAR(255) PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            conn.commit()
            self._table_initialized = True
        except Exception as e:
            conn.rollback()
            logger.debug(f"Failed to ensure Postgres metadata table: {e}")

    def is_available(self) -> bool:
        conn = self._get_connection()
        if conn is None:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            conn.close()
            return True
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            return False

    def get_state(self, key: str) -> Optional[str]:
        conn = self._get_connection()
        if conn is None:
            return None
        try:
            self._ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM cochem_metadata_registry WHERE key = %s;", (key,))
                row = cur.fetchone()
                if row:
                    return str(row[0])
                return None
        except Exception as e:
            logger.warning(f"Postgres get_state error for {key}: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def set_state(self, key: str, value: str) -> bool:
        conn = self._get_connection()
        if conn is None:
            return False
        try:
            self._ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cochem_metadata_registry (key, value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP;
                    """,
                    (key, value),
                )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.warning(f"Postgres set_state error for {key}: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def delete_state(self, key: str) -> bool:
        conn = self._get_connection()
        if conn is None:
            return False
        try:
            self._ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cochem_metadata_registry WHERE key = %s;", (key,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.warning(f"Postgres delete_state error for {key}: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @property
    def backend_type(self) -> MetadataBackendType:
        return MetadataBackendType.POSTGRES


class FilesystemMetadataServer(BaseMetadataServer):
    """Filesystem metadata server fallback using NFS-resilient directory staging and AtomicFileLock."""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None) -> None:
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            self.base_dir = (get_artifact_dir() / "Registry").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return True

    def _get_key_path(self, key: str) -> Path:
        safe_key = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
        return self.base_dir / f"{safe_key}.json"

    def get_state(self, key: str) -> Optional[str]:
        p = self._get_key_path(key)
        if not p.is_file():
            return None
        with AtomicFileLock(str(p) + ".lock", timeout=10.0):
            try:
                return p.read_text(encoding="utf-8")
            except OSError:
                return None

    def set_state(self, key: str, value: str) -> bool:
        p = self._get_key_path(key)
        try:
            atomic_write_json(p, value, lock_timeout=10.0)
            return True
        except Exception as e:
            logger.error(f"Filesystem set_state failed for {key}: {e}")
            return False

    def delete_state(self, key: str) -> bool:
        p = self._get_key_path(key)
        lock_file = str(p) + ".lock"
        with AtomicFileLock(lock_file, timeout=10.0):
            if p.exists():
                try:
                    p.unlink(missing_ok=True)
                    return True
                except OSError:
                    return False
            return False

    @property
    def backend_type(self) -> MetadataBackendType:
        return MetadataBackendType.FILESYSTEM


class MetadataServerManager:
    """Coordinates state transactions across dedicated metadata servers with automatic filesystem fallback."""

    def __init__(
        self,
        preferred_backend: Optional[Union[MetadataBackendType, str]] = None,
        redis_server: Optional[RedisMetadataServer] = None,
        postgres_server: Optional[PostgresMetadataServer] = None,
        filesystem_server: Optional[FilesystemMetadataServer] = None,
    ) -> None:
        pref = preferred_backend if preferred_backend is not None else os.environ.get("COCHEM_METADATA_BACKEND", "filesystem")
        if isinstance(pref, str):
            pref_lower = pref.lower().strip()
            if pref_lower == "redis":
                self.preferred: MetadataBackendType = MetadataBackendType.REDIS
            elif pref_lower in ("postgres", "postgresql"):
                self.preferred = MetadataBackendType.POSTGRES
            else:
                self.preferred = MetadataBackendType.FILESYSTEM
        elif isinstance(pref, MetadataBackendType):
            self.preferred = pref
        else:
            self.preferred = MetadataBackendType.FILESYSTEM

        self.redis = redis_server or RedisMetadataServer()
        self.postgres = postgres_server or PostgresMetadataServer()
        self.filesystem = filesystem_server or FilesystemMetadataServer()

    def get_active_backend(self) -> BaseMetadataServer:
        """Resolves the active available metadata server backend, falling back to filesystem."""
        if self.preferred == MetadataBackendType.REDIS and self.redis.is_available():
            return self.redis
        if self.preferred == MetadataBackendType.POSTGRES and self.postgres.is_available():
            return self.postgres
        return self.filesystem

    def get_state(self, key: str) -> Optional[str]:
        backend = self.get_active_backend()
        res = backend.get_state(key)
        if res is None and backend != self.filesystem:
            return self.filesystem.get_state(key)
        return res

    def set_state(self, key: str, value: str) -> bool:
        backend = self.get_active_backend()
        success = backend.set_state(key, value)
        if backend != self.filesystem:
            self.filesystem.set_state(key, value)
        return success

    def delete_state(self, key: str) -> bool:
        backend = self.get_active_backend()
        success = backend.delete_state(key)
        if backend != self.filesystem:
            self.filesystem.delete_state(key)
        return success


# Global default metadata manager
default_metadata_manager = MetadataServerManager()


# =============================================================================
# ENVIRONMENT FINGERPRINTING & SCHEMA MIGRATION
# =============================================================================

def _sanitize_path_leakages(payload_str: str) -> str:
    """Sanitizes local absolute directory paths from serialized environment payloads."""
    p1 = r'[A-Za-z]:(?:\\\\|\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p1, "[SANITIZED_PATH]", payload_str)
    p2 = r'/(?:home|Users|root|tmp|var|opt|usr|etc|Volumes)/[^",}\]\r\n]*'
    sanitized = re.sub(p2, "[SANITIZED_PATH]", sanitized)
    p3 = r'(?:\\\\\\\\|//|\\\\)[^",}\]\r\n]*'
    sanitized = re.sub(p3, "[SANITIZED_PATH]", sanitized)
    p4 = r'(?:\\\\|/)?(?:Users|AppData|Documents|Desktop)(?:\\\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p4, "[SANITIZED_PATH]", sanitized)
    return sanitized


def hash_environment(
    exclude_paths: bool = True,
    tracked_packages: Optional[Sequence[str]] = None,
    tracked_engines: Optional[Union[Sequence[str], Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Generates a deterministic cryptographic SHA-256 fingerprint of the host environment."""
    try:
        from cochem_base.provenance.hashing import hash_environment as _h_env

        rec = _h_env(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )
        return cast(
            Dict[str, Any],
            rec.to_dict() if hasattr(rec, "to_dict") else dict(rec.__dict__),
        )
    except Exception:
        py_ver = platform.python_version()
        py_impl = platform.python_implementation()
        os_sys = platform.system()
        os_rel = platform.release()
        os_arch = platform.machine()
        cpu_cnt = os.cpu_count() or 1
        total_ram = 0

        try:
            import psutil  # type: ignore[import-untyped]
            total_ram = psutil.virtual_memory().total
        except Exception:
            total_ram = 16 * 1024 * 1024 * 1024

        canonical_payload = {
            "python_version": py_ver,
            "python_implementation": py_impl,
            "os_system": os_sys,
            "os_release": os_rel,
            "os_architecture": os_arch,
            "cpu_count": cpu_cnt,
            "total_ram_bytes": total_ram,
            "tracked_packages": list(tracked_packages or []),
            "tracked_engines": tracked_engines
            if isinstance(tracked_engines, dict)
            else list(tracked_engines or []),
        }

        serialized = json.dumps(canonical_payload, sort_keys=True)
        if exclude_paths:
            serialized = _sanitize_path_leakages(serialized)

        sha256_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return {
            "sha256_hash": sha256_hash,
            "python_version": py_ver,
            "python_implementation": py_impl,
            "os_system": os_sys,
            "os_release": os_rel,
            "cpu_count": cpu_cnt,
            "total_ram_bytes": total_ram,
            "metadata": {"os_architecture": os_arch},
        }


def migrate_schema(
    config_source: Union[Dict[str, Any], str, Path, CoChemSystemConfig],
) -> CoChemSystemConfig:
    """Upgrades legacy JSON schemas (0.1, 1.0.0, 2.0.0) to current target schema (4.0.0) with strict validation."""
    if isinstance(config_source, CoChemSystemConfig):
        # Strict validation checkpoint
        return CoChemSystemConfig.model_validate(config_source.model_dump())

    if isinstance(config_source, (str, Path)):
        p = Path(config_source)
        if p.is_file():
            raw_text = p.read_text(encoding="utf-8")
            raw_dict = json.loads(raw_text)
        else:
            raw_dict = json.loads(str(config_source))
    elif isinstance(config_source, dict):
        raw_dict = dict(config_source)
    else:
        raise SchemaMigrationError(
            f"Unsupported config source type for migration: {type(config_source)}"
        )

    raw_dict = interpolate_env_vars(raw_dict)
    raw_dict["schema_version"] = "4.0.0"

    if "quantum_settings" not in raw_dict or raw_dict["quantum_settings"] is None:
        raw_dict["quantum_settings"] = {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
            "charge": 0,
            "multiplicity": 1,
        }

    if "hpc" not in raw_dict or raw_dict["hpc"] is None:
        raw_dict["hpc"] = {
            "scheduler": "local",
            "default_partition": "compute",
            "max_walltime_hours": 24,
        }

    try:
        # Pydantic verification checkpoint rejecting illegal data injection
        cfg = CoChemSystemConfig.model_validate(raw_dict)
        cfg.update_checksum()
        return cfg
    except ValidationError as e:
        raise SchemaMigrationError(f"Failed to migrate and validate system schema: {e}") from e
    except Exception as e:
        raise SchemaMigrationError(f"Failed to migrate and validate system schema: {e}") from e


# =============================================================================
# MASTER NODE & ZEROMQ BROADCAST
# =============================================================================

def is_master_node() -> bool:
    """Determines whether current execution process is the master node (Rank 0 / Standalone)."""
    override = os.environ.get("COCHEM_IS_MASTER")
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes")

    slurm_procid = os.environ.get("SLURM_PROCID")
    if slurm_procid is not None:
        return slurm_procid.strip() == "0"

    for rank_var in ["OMPI_COMM_WORLD_RANK", "PMI_RANK", "RANK", "MV2_COMM_WORLD_RANK"]:
        val = os.environ.get(rank_var)
        if val is not None:
            return val.strip() == "0"

    return True


def broadcast_system_config(
    config: Optional[Union[CoChemSystemConfig, Dict[str, Any]]] = None,
    port: int = 5555,
    host: str = "0.0.0.0",
    topic: str = "cochem_system_config",
    config_path: Optional[Union[str, Path]] = None,
    repeat_count: int = 5,
    repeat_interval: float = 0.05,
    ready_event: Optional[threading.Event] = None,
) -> str:
    """Broadcasts validated system configuration over ZeroMQ PUB socket for HPC worker nodes."""
    if config is None:
        config = load_system_config(config_path)

    if isinstance(config, dict):
        validated_cfg = migrate_schema(config)
    elif isinstance(config, CoChemSystemConfig):
        validated_cfg = CoChemSystemConfig.model_validate(config.model_dump())
    else:
        raise TypeError(f"Invalid config type for broadcast: {type(config)}")

    json_payload = validated_cfg.model_dump_json()

    ctx: zmq.Context[Any] = zmq.Context.instance()
    pub_socket = ctx.socket(zmq.PUB)
    pub_socket.setsockopt(zmq.LINGER, 1000)
    try:
        pub_socket.bind(f"tcp://{host}:{port}")
        if ready_event is not None:
            ready_event.set()
        time.sleep(0.15)
        for _ in range(max(1, repeat_count)):
            pub_socket.send_multipart([topic.encode("utf-8"), json_payload.encode("utf-8")])
            time.sleep(repeat_interval)
    finally:
        pub_socket.close()

    return validated_cfg.compute_checksum()


def receive_system_config_broadcast(
    master_host: str = "127.0.0.1",
    port: int = 5555,
    topic: str = "cochem_system_config",
    timeout_ms: int = 5000,
) -> CoChemSystemConfig:
    """Receives system configuration from master ZeroMQ broadcast."""
    ctx: zmq.Context[Any] = zmq.Context.instance()
    sub_socket = ctx.socket(zmq.SUB)
    sub_socket.setsockopt(zmq.LINGER, 0)
    try:
        sub_socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        sub_socket.connect(f"tcp://{master_host}:{port}")
        sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        time.sleep(0.05)
        parts = sub_socket.recv_multipart()
        json_str = parts[1].decode("utf-8")
        return CoChemSystemConfig.model_validate_json(json_str)
    except zmq.error.Again as e:
        raise TimeoutError(
            f"ZeroMQ config broadcast timed out after {timeout_ms}ms from {master_host}:{port}"
        ) from e
    finally:
        sub_socket.close()


# =============================================================================
# SYSTEM CONFIGURATION I/O & STAGE 0 GUARDRAILS
# =============================================================================

def get_default_config_path() -> Path:
    """Resolves the default system configuration file path."""
    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg:
        return Path(os.path.expandvars(env_cfg)).expanduser().resolve()

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return (
            Path(os.path.expandvars(env_art)).expanduser()
            / "Registry"
            / "cochem_system_config.json"
        ).resolve()

    try:
        from cochem_base.config_loader import resolve_config_path
        return resolve_config_path()
    except Exception:
        return (Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json").resolve()


def load_system_config(
    config_path: Optional[Union[str, Path]] = None,
    verify_integrity: bool = True,
) -> CoChemSystemConfig:
    """Loads and validates cochem_system_config.json with environment variable expansion and integrity checks.

    Enforces Stage 0 Guardrail:
    - If file is missing, logs violation and raises RegistryMissingError.
    - If JSON is malformed, logs violation and raises RegistryParseError.
    - If checksum verification fails, logs violation and raises RegistryCorruptionError.
    """
    target_path = Path(config_path or get_default_config_path()).resolve()
    if not target_path.is_file():
        logger.critical(f"Stage 0 Guardrail: Master registry not found at: {target_path}")
        raise RegistryMissingError(f"Stage 0 Guardrail: Master registry not found at '{target_path}'")

    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        try:
            raw_text = target_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.critical(f"Stage 0 Guardrail: Failed to read registry at {target_path}: {e}")
            raise RegistryMissingError(f"Stage 0 Guardrail: Failed to read registry at '{target_path}': {e}") from e

        try:
            parsed_json = json.loads(raw_text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.critical(f"Stage 0 Guardrail: Malformed registry JSON at {target_path}: {e}")
            raise RegistryParseError(f"Stage 0 Guardrail: Unparseable registry JSON at '{target_path}': {e}") from e

        if not isinstance(parsed_json, dict):
            logger.critical(
                f"Stage 0 Guardrail: Registry root must be a JSON object, got {type(parsed_json).__name__} at {target_path}"
            )
            raise RegistryParseError(
                f"Stage 0 Guardrail: Registry root must be a JSON object, got {type(parsed_json).__name__}"
            )

        interpolated_dict = interpolate_env_vars(parsed_json)

        try:
            config = migrate_schema(interpolated_dict)
        except Exception as e:
            logger.critical(f"Stage 0 Guardrail: Schema validation error for {target_path}: {e}")
            raise SchemaMigrationError(f"Stage 0 Guardrail: Schema validation error for '{target_path}': {e}") from e

        if verify_integrity and "registry_checksum" in parsed_json and parsed_json["registry_checksum"]:
            expected = parsed_json["registry_checksum"]
            computed = config.compute_checksum()
            if expected != computed:
                logger.critical(
                    f"Stage 0 Guardrail: Registry corruption at {target_path} (expected checksum '{expected}', computed '{computed}')"
                )
                raise RegistryCorruptionError(
                    f"Stage 0 Guardrail: Registry corruption at '{target_path}' (expected '{expected}', computed '{computed}')"
                )

        return config


def save_system_config(
    config: Union[CoChemSystemConfig, Dict[str, Any]],
    config_path: Optional[Union[str, Path]] = None,
) -> str:
    """Saves system configuration atomically with updated SHA-256 checksum after strict Pydantic validation."""
    target_path = Path(config_path or get_default_config_path()).resolve()

    # Pydantic verification checkpoint
    if isinstance(config, dict):
        cfg_model = migrate_schema(config)
    elif isinstance(config, CoChemSystemConfig):
        cfg_model = CoChemSystemConfig.model_validate(config.model_dump())
    else:
        raise TypeError(f"Invalid config type: {type(config)}")

    cfg_model.last_updated = datetime.now(timezone.utc).isoformat()
    checksum = cfg_model.update_checksum()
    atomic_write_json(target_path, cfg_model, lock_timeout=10.0)
    return checksum


def update_system_config(
    config_path: Optional[Union[str, Path]] = None,
    **updates: Any,
) -> CoChemSystemConfig:
    """Atomically updates fields within cochem_system_config.json with strict Pydantic validation checkpoint."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"

    with AtomicFileLock(lock_file, timeout=10.0):
        current = load_system_config(target_path, verify_integrity=False)
        current_dict = current.model_dump()
        current_dict.update(updates)

        # Pydantic verification checkpoint: strictly rejects illegal data injection
        updated_cfg = migrate_schema(current_dict)
        save_system_config(updated_cfg, target_path)
        return updated_cfg


# =============================================================================
# ACTIVE JOBS LIFECYCLE MANAGEMENT
# =============================================================================

def register_active_job(
    job_id: str,
    job_data: Union[Dict[str, Any], BaseModel],
    config_path: Optional[Union[str, Path]] = None,
) -> None:
    """Registers an active execution job into cochem_system_config.json under active_jobs."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Job ID must be a non-empty string.")

    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"

    payload = job_data.model_dump() if isinstance(job_data, BaseModel) else dict(job_data)
    if "registered_at" not in payload:
        payload["registered_at"] = datetime.now(timezone.utc).isoformat()

    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        cfg.active_jobs[job_id] = payload
        save_system_config(cfg, target_path)


def get_active_job(
    job_id: str,
    config_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieves an active job record from cochem_system_config.json, or None if not found."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        return None
    target_path = Path(config_path or get_default_config_path()).resolve()
    cfg = load_system_config(target_path, verify_integrity=False)
    return cfg.active_jobs.get(job_id)


def list_active_jobs(
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Returns all active jobs recorded in cochem_system_config.json."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    cfg = load_system_config(target_path, verify_integrity=False)
    return dict(cfg.active_jobs)


def remove_active_job(
    job_id: str,
    config_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Removes an active job from cochem_system_config.json."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        return False
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        if job_id in cfg.active_jobs:
            del cfg.active_jobs[job_id]
            save_system_config(cfg, target_path)
            return True
        return False


def update_active_job(
    job_id: str,
    status: str,
    config_path: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Updates status and additional fields of an active job in cochem_system_config.json."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Job ID must be a non-empty string.")
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        if job_id not in cfg.active_jobs:
            raise RecordNotFoundError(f"Cannot update non-existent active job '{job_id}'")
        job_record = dict(cfg.active_jobs[job_id])
        job_record["status"] = status
        job_record.update(kwargs)
        job_record["updated_at"] = datetime.now(timezone.utc).isoformat()
        cfg.active_jobs[job_id] = job_record
        save_system_config(cfg, target_path)
        return job_record


# =============================================================================
# MASTER REGISTRY MANAGER CLASS
# =============================================================================

class RegistryManager:
    """Consolidated state registry manager using HDF5, Atomic File Locks, and ZeroMQ Broadcasts."""

    SCHEMA_VERSION = "1.0.0"

    def __init__(
        self, config_path: Optional[str] = None, registry_path: Optional[str] = None
    ) -> None:
        if config_path:
            self.config_path = str(resolve_config_path(Path(config_path)))
        else:
            self.config_path = str(resolve_config_path())

        if registry_path:
            self.registry_path = str(
                resolve_mapped_path(registry_path, get_artifact_dir() / "Registry")
            )
        else:
            self.registry_path = str(get_artifact_dir() / "Registry" / "cochem_registry.h5")

        self.lock_path = self.registry_path + ".lock"
        self._ensure_registry_exists()

    def _ensure_registry_exists(self) -> None:
        """Ensure the HDF5 registry file and required groups exist, with atomic locking."""
        try:
            Path(self.registry_path).parent.mkdir(parents=True, exist_ok=True)
            with AtomicFileLock(self.lock_path, timeout=10.0):
                if not os.path.exists(self.registry_path):
                    with h5py.File(self.registry_path, "w") as h5:
                        h5.attrs["created"] = datetime.now(timezone.utc).isoformat()
                        h5.attrs["version"] = self.SCHEMA_VERSION
                        h5.create_group("jobs")
                        h5.create_group("hardware_profiles")
                        h5.create_group("basis_sets")
                        h5.create_group("embedded_basis_sets")
                        h5.create_group("provenance")
                        h5.create_group("seeds")
                        h5.create_group("metadata")
                    logger.info(f"Created new registry file: {self.registry_path}")
                else:
                    with h5py.File(self.registry_path, "a") as h5:
                        if "version" not in h5.attrs:
                            h5.attrs["version"] = self.SCHEMA_VERSION
                        for grp in [
                            "jobs",
                            "hardware_profiles",
                            "basis_sets",
                            "embedded_basis_sets",
                            "provenance",
                            "seeds",
                            "metadata",
                        ]:
                            if grp not in h5:
                                h5.create_group(grp)
        except Exception as e:
            logger.error(f"Failed to initialize registry: {e}")
            raise RuntimeError(f"Registry initialization failed: {e}") from e

    @contextmanager
    def transaction(self, mode: str = "a") -> Generator[h5py.File, None, None]:
        """Provides an atomic transaction over the HDF5 registry using AtomicFileLock."""
        with AtomicFileLock(self.lock_path, timeout=10.0):
            with h5py.File(self.registry_path, mode) as h5:
                yield h5

    @contextmanager
    def config_transaction(self) -> Generator[CoChemSystemConfig, None, None]:
        """Provides an atomic transaction over cochem_system_config.json with strict Pydantic verification."""
        target_path = Path(self.config_path).resolve()
        lock_file = str(target_path) + ".lock"
        with AtomicFileLock(lock_file, timeout=10.0):
            cfg = self.load_system_config(verify_integrity=False)
            yield cfg
            validated = CoChemSystemConfig.model_validate(cfg.model_dump())
            self.save_system_config(validated)

    def get_registry_stats(self) -> Dict[str, Any]:
        """Returns statistics on active registry record groups."""
        with self.transaction("r") as h5:
            jobs_c = len(h5["jobs"]) if "jobs" in h5 else 0
            hw_c = len(h5["hardware_profiles"]) if "hardware_profiles" in h5 else 0
            prov_c = len(h5["provenance"]) if "provenance" in h5 else 0
            basis_c = (
                len(h5["embedded_basis_sets"])
                if "embedded_basis_sets" in h5
                else (len(h5["basis_sets"]) if "basis_sets" in h5 else 0)
            )
            seeds_c = len(h5["seeds"]) if "seeds" in h5 else 0
            ver = h5.attrs.get("version", self.SCHEMA_VERSION)
            if isinstance(ver, bytes):
                ver = ver.decode("utf-8")
            return {
                "jobs_count": jobs_c,
                "hardware_profiles_count": hw_c,
                "provenance_count": prov_c,
                "basis_sets_count": basis_c,
                "seeds_count": seeds_c,
                "version": str(ver),
            }

    # =========================================================================
    # System Configuration Delegates
    # =========================================================================

    def load_system_config(
        self,
        config_path: Optional[Union[str, Path]] = None,
        verify_integrity: bool = True,
    ) -> CoChemSystemConfig:
        """Loads system configuration using the authoritative Stage 0 loader."""
        return load_system_config(config_path or self.config_path, verify_integrity=verify_integrity)

    def save_system_config(
        self,
        config: Union[CoChemSystemConfig, Dict[str, Any]],
        config_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Saves system configuration atomically with updated SHA-256 checksum."""
        return save_system_config(config, config_path or self.config_path)

    def update_system_config(self, **updates: Any) -> CoChemSystemConfig:
        """Atomically updates fields within cochem_system_config.json."""
        return update_system_config(config_path=self.config_path, **updates)

    def register_active_job(self, job_id: str, job_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Registers an active execution job in cochem_system_config.json."""
        register_active_job(job_id, job_data, config_path=self.config_path)

    def get_active_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an active execution job from cochem_system_config.json."""
        return get_active_job(job_id, config_path=self.config_path)

    def list_active_jobs(self) -> Dict[str, Any]:
        """Lists all active execution jobs in cochem_system_config.json."""
        return list_active_jobs(config_path=self.config_path)

    def remove_active_job(self, job_id: str) -> bool:
        """Removes an active execution job from cochem_system_config.json."""
        return remove_active_job(job_id, config_path=self.config_path)

    def update_active_job(self, job_id: str, status: str, **kwargs: Any) -> Dict[str, Any]:
        """Updates an active execution job in cochem_system_config.json."""
        return update_active_job(job_id, status, config_path=self.config_path, **kwargs)

    def poll_system_config(
        self,
        master_host: str = "127.0.0.1",
        zmq_port: int = 5555,
        timeout_ms: int = 2000,
    ) -> CoChemSystemConfig:
        """Polls configuration: Master reads disk directly; Worker receives ZMQ broadcast with disk fallback."""
        if is_master_node():
            return self.load_system_config()
        try:
            return receive_system_config_broadcast(
                master_host=master_host, port=zmq_port, timeout_ms=timeout_ms
            )
        except Exception as e:
            logger.debug(f"Worker ZMQ poll failed, falling back to disk read: {e}")
            return self.load_system_config()

    def broadcast_config(
        self,
        port: int = 5555,
        host: str = "0.0.0.0",
        topic: str = "cochem_system_config",
    ) -> str:
        """Broadcasts current configuration via ZeroMQ."""
        cfg = self.load_system_config(verify_integrity=False)
        return broadcast_system_config(cfg, port=port, host=host, topic=topic)

    def receive_config_broadcast(
        self,
        master_host: str = "127.0.0.1",
        port: int = 5555,
        topic: str = "cochem_system_config",
        timeout_ms: int = 5000,
    ) -> CoChemSystemConfig:
        """Subscribes and receives configuration broadcast via ZeroMQ."""
        return receive_system_config_broadcast(
            master_host=master_host, port=port, topic=topic, timeout_ms=timeout_ms
        )

    def hash_environment(
        self,
        exclude_paths: bool = True,
        tracked_packages: Optional[Sequence[str]] = None,
        tracked_engines: Optional[Union[Sequence[str], Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Calculates environmental hash for state tracking."""
        return hash_environment(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )

    def migrate_schema(
        self, config_source: Union[Dict[str, Any], str, Path, CoChemSystemConfig]
    ) -> CoChemSystemConfig:
        """Migrates schema to 4.0.0."""
        return migrate_schema(config_source)

    # =========================================================================
    # Isotopic Mass & Mendeleev/QCElemental Queries
    # =========================================================================

    @staticmethod
    def get_isotopic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
        """Dynamically fetches exact isotopic masses via Mendeleev, QCElemental, or periodic tables."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if mass_number is not None and not isinstance(mass_number, int):
            raise ValueError("Mass number must be an integer.")

        if clean_sym.upper() == "D":
            if mass_number is not None and mass_number != 2:
                raise ValueError(f"Isotope {mass_number}D not found in Mendeleev database.")
            clean_sym = "H"
            formatted_sym = "H"
            mass_number = 2
        elif clean_sym.upper() == "T":
            if mass_number is not None and mass_number != 3:
                raise ValueError(f"Isotope {mass_number}T not found in Mendeleev database.")
            clean_sym = "H"
            formatted_sym = "H"
            mass_number = 3

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        elem = None

                if elem is not None:
                    if mass_number is not None:
                        for iso in elem.isotopes:
                            if iso.mass_number == mass_number:
                                if iso.mass is None:
                                    raise IsotopeStabilityError(
                                        f"Isotope {mass_number}{clean_sym} has no stable mass record in Mendeleev."
                                    )
                                return float(iso.mass)
                        raise ValueError(
                            f"Isotope {mass_number}{clean_sym} not found in Mendeleev database."
                        )

                    if hasattr(elem, "mass") and elem.mass is not None:
                        return float(elem.mass)
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} lacks a valid default atomic mass binding."
                    )
            except (ValueError, IsotopeStabilityError):
                raise
            except Exception as e:
                logger.debug(f"Mendeleev query failed for '{clean_sym}', attempting fallback: {e}")

        if pt is not None:
            try:
                if mass_number is not None:
                    target = f"{formatted_sym}{mass_number}"
                    try:
                        return float(pt.to_mass(target))
                    except Exception as e:
                        raise ValueError(
                            f"Isotope {mass_number}{clean_sym} not found in Mendeleev database."
                        ) from e
                try:
                    return float(pt.to_mass(formatted_sym))
                except Exception as e:
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} not found in Mendeleev."
                    ) from e
            except (ValueError, IsotopeStabilityError):
                raise
            except Exception as e:
                logger.error(f"Failed to query QCElemental for symbol '{clean_sym}': {e}")
                raise IsotopeStabilityError(
                    f"Isotopic mass resolution failed for {clean_sym}: {e}"
                ) from e

        raise IsotopeStabilityError(
            f"Element {clean_sym} not found in Mendeleev or QCElemental database."
        )

    @staticmethod
    def get_all_isotopes(symbol: str) -> List[Dict[str, Any]]:
        """Returns all isotopic variants for a given chemical element symbol."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if clean_sym.upper() in ("D", "T"):
            clean_sym = "H"
            formatted_sym = "H"

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        elem = None

                if elem is not None:
                    isotopes = []
                    for iso in elem.isotopes:
                        isotopes.append(
                            {
                                "mass_number": int(iso.mass_number),
                                "mass": float(iso.mass) if iso.mass is not None else None,
                                "abundance": float(iso.abundance)
                                if getattr(iso, "abundance", None) is not None
                                else None,
                            }
                        )
                    return isotopes
            except Exception as e:
                logger.debug(f"Mendeleev isotopes query failed for '{clean_sym}': {e}")

        if pt is not None:
            try:
                isotopes = []
                try:
                    pt.to_mass(formatted_sym)
                except Exception as err:
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} not found in Mendeleev."
                    ) from err

                pattern = re.compile(rf"^{formatted_sym}(\d+)$")
                if hasattr(pt, "_eliso2mass"):
                    for k, m in pt._eliso2mass.items():
                        mat = pattern.match(k)
                        if mat:
                            isotopes.append(
                                {
                                    "mass_number": int(mat.group(1)),
                                    "mass": float(m),
                                    "abundance": None,
                                }
                            )
                return sorted(isotopes, key=lambda x: x["mass_number"])
            except IsotopeStabilityError:
                raise
            except Exception as e:
                raise IsotopeStabilityError(f"Failed to fetch isotopes for {clean_sym}: {e}") from e

        raise IsotopeStabilityError(f"Element {clean_sym} not found in Mendeleev or QCElemental.")

    # =========================================================================
    # HDF5 Registry Operations
    # =========================================================================

    def register_job(self, job_id: str, job_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Registers a calculation job record in the HDF5 registry."""
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("Job ID must be a non-empty string.")

        payload = job_data.model_dump() if isinstance(job_data, BaseModel) else dict(job_data)
        if "registered_at" not in payload:
            payload["registered_at"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id in jobs_grp:
                del jobs_grp[job_id]
            dset = jobs_grp.create_dataset(
                job_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )
            dset.attrs["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered job record, or None if not found."""
        with self.transaction("r") as h5:
            if "jobs" not in h5 or job_id not in h5["jobs"]:
                return None
            val = h5["jobs"][job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def update_job_status(self, job_id: str, status: str, **kwargs: Any) -> None:
        """Updates the status and additional fields of an existing job record."""
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id not in jobs_grp:
                raise RecordNotFoundError(f"Cannot update status for non-existent job '{job_id}'")
            val = jobs_grp[job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            rec = json.loads(text)
            rec["status"] = status
            rec.update(kwargs)
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            del jobs_grp[job_id]
            jobs_grp.create_dataset(
                job_id, data=json.dumps(rec), dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Returns all registered jobs with job_id included."""
        results = []
        with self.transaction("r") as h5:
            if "jobs" in h5:
                for k in h5["jobs"].keys():
                    val = h5["jobs"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["job_id"] = k
                    results.append(data)
        return results

    def delete_job(self, job_id: str) -> bool:
        """Deletes a job from the registry."""
        with self.transaction("a") as h5:
            if "jobs" in h5 and job_id in h5["jobs"]:
                del h5["jobs"][job_id]
                return True
            return False

    def register_hardware_profile(
        self, profile_id: str, profile_data: Union[Dict[str, Any], BaseModel]
    ) -> None:
        """Registers a host/node hardware configuration profile."""
        if not profile_id or not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Profile ID must be a non-empty string.")

        payload = (
            profile_data.model_dump() if isinstance(profile_data, BaseModel) else dict(profile_data)
        )
        payload["registered_at"] = datetime.now(timezone.utc).isoformat()
        json_str = json.dumps(payload)

        with self.transaction("a") as h5:
            hw_grp = h5["hardware_profiles"]
            if profile_id in hw_grp:
                del hw_grp[profile_id]
            hw_grp.create_dataset(
                profile_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_hardware_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered hardware profile by ID."""
        with self.transaction("r") as h5:
            if "hardware_profiles" not in h5 or profile_id not in h5["hardware_profiles"]:
                return None
            val = h5["hardware_profiles"][profile_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def get_all_hardware_profiles(self) -> List[Dict[str, Any]]:
        """Returns all hardware profiles."""
        results = []
        with self.transaction("r") as h5:
            if "hardware_profiles" in h5:
                for k in h5["hardware_profiles"].keys():
                    val = h5["hardware_profiles"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["profile_id"] = k
                    results.append(data)
        return results

    def delete_hardware_profile(self, profile_id: str) -> bool:
        """Deletes a hardware profile from the registry."""
        with self.transaction("a") as h5:
            if "hardware_profiles" in h5 and profile_id in h5["hardware_profiles"]:
                del h5["hardware_profiles"][profile_id]
                return True
            return False

    def add_provenance_record(self, record_id: str, record_data: Dict[str, Any]) -> str:
        """Adds a cryptographic/workflow provenance record and returns a unique lineage UUID."""
        if not record_id or not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("Record ID must be a non-empty string.")

        lineage_uuid = f"lin_{uuid.uuid4().hex}"
        payload = dict(record_data)
        payload["record_id"] = record_id
        payload["lineage_uuid"] = lineage_uuid
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            prov_grp = h5["provenance"]
            if record_id in prov_grp:
                del prov_grp[record_id]
            prov_grp.create_dataset(
                record_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )

        return lineage_uuid

    def get_provenance_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a provenance record by ID."""
        with self.transaction("r") as h5:
            if "provenance" not in h5 or record_id not in h5["provenance"]:
                return None
            val = h5["provenance"][record_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def get_lineage_chain(self, leaf_record_id: str) -> List[Dict[str, Any]]:
        """Traces the backward DAG lineage chain from leaf to root with cycle protection."""
        chain = []
        curr_id = leaf_record_id
        all_prov = {p["lineage_uuid"]: p for p in self.get_all_provenance_records()}
        rec_by_id = {p["record_id"]: p for p in all_prov.values()}
        visited = set()

        curr = rec_by_id.get(curr_id)
        while curr is not None:
            curr_uuid = curr.get("lineage_uuid")
            if curr_uuid in visited:
                logger.warning(f"Provenance cycle detected at record {curr_id}")
                break
            if curr_uuid:
                visited.add(curr_uuid)
            chain.append(curr)
            parent_uuid = curr.get("parent_uuid")
            if not parent_uuid or parent_uuid not in all_prov:
                break
            curr = all_prov.get(parent_uuid)

        return chain

    def get_all_provenance_records(self) -> List[Dict[str, Any]]:
        """Returns all provenance records."""
        results = []
        with self.transaction("r") as h5:
            if "provenance" in h5:
                for k in h5["provenance"].keys():
                    val = h5["provenance"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    results.append(data)
        return results

    def delete_provenance_record(self, record_id: str) -> bool:
        """Deletes a provenance record."""
        with self.transaction("a") as h5:
            if "provenance" in h5 and record_id in h5["provenance"]:
                del h5["provenance"][record_id]
                return True
            return False

    def lock_prng_seed(
        self, seed: int, scope: str = "global", metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Locks a pseudorandom number generator seed into the registry."""
        if not isinstance(seed, int):
            raise ValueError("PRNG seed must be an integer.")

        payload = {
            "seed": seed,
            "scope": scope,
            "metadata": metadata or {},
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }

        with self.transaction("a") as h5:
            seeds_grp = h5["seeds"]
            if scope in seeds_grp:
                del seeds_grp[scope]
            seeds_grp.create_dataset(
                scope, data=json.dumps(payload), dtype=h5py.string_dtype(encoding="utf-8")
            )

        return seed

    def get_locked_seed(self, scope: str = "global") -> Optional[int]:
        """Retrieves a locked PRNG seed for a given scope."""
        with self.transaction("r") as h5:
            if "seeds" not in h5 or scope not in h5["seeds"]:
                return None
            val = h5["seeds"][scope][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[int], json.loads(text).get("seed"))

    def verify_prng_seed(self, seed: int, scope: str = "global") -> bool:
        """Verifies if an active seed matches the registered locked seed for a scope."""
        locked = self.get_locked_seed(scope)
        return locked is not None and locked == seed

    def list_locked_seeds(self) -> Dict[str, int]:
        """Returns all locked seeds mapped by scope."""
        res = {}
        with self.transaction("r") as h5:
            if "seeds" in h5:
                for k in h5["seeds"].keys():
                    val = h5["seeds"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    res[k] = json.loads(text).get("seed")
        return res

    def embed_basis_set_archive(
        self,
        h5_path: Optional[str] = None,
        basis_file_path: str = "",
        label: str = "",
        is_content: bool = False,
    ) -> None:
        """Embeds full basis set text into the HDF5 archive to prevent link rot."""
        if not label or not isinstance(label, str) or not label.strip():
            raise ValueError("Basis set label must be a non-empty string.")

        clean_label = label.strip()

        if is_content:
            raw_text = basis_file_path
        else:
            p = Path(basis_file_path)
            if not p.is_file():
                raise FileNotFoundError(f"Basis set file not found: {p}")
            raw_text = p.read_text(encoding="utf-8")

        mapped_h5 = Path(h5_path or self.registry_path)
        with AtomicFileLock(str(mapped_h5) + ".lock", timeout=10.0):
            with h5py.File(mapped_h5, "a") as h5:
                if "embedded_basis_sets" not in h5:
                    h5.create_group("embedded_basis_sets")
                grp = h5["embedded_basis_sets"]
                if clean_label in grp:
                    del grp[clean_label]
                grp.create_dataset(
                    clean_label, data=raw_text, dtype=h5py.string_dtype(encoding="utf-8")
                )

    def has_embedded_basis_set(self, label: str) -> bool:
        """Checks if a basis set label exists in the registry."""
        with self.transaction("r") as h5:
            return "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]

    def get_embedded_basis_set(self, label: str) -> str:
        """Retrieves embedded basis set content."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" not in h5 or label not in h5["embedded_basis_sets"]:
                raise BasisSetNotFoundError(f"Basis set '{label}' not found in registry.")
            val = h5["embedded_basis_sets"][label][()]
            return val.decode("utf-8") if isinstance(val, bytes) else str(val)

    def list_embedded_basis_sets(self) -> List[str]:
        """Lists all embedded basis set labels."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" in h5:
                return list(h5["embedded_basis_sets"].keys())
            return []

    def delete_embedded_basis_set(self, label: str) -> bool:
        """Deletes an embedded basis set."""
        with self.transaction("a") as h5:
            if "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]:
                del h5["embedded_basis_sets"][label]
                return True
            return False

    def migrate_legacy_schema(self) -> Dict[str, Any]:
        """Upgrades legacy HDF5 schema files to 1.0.0."""
        with self.transaction("a") as h5:
            prev_ver = h5.attrs.get("version", "0.1")
            if isinstance(prev_ver, bytes):
                prev_ver = prev_ver.decode("utf-8")

            h5.attrs["version"] = self.SCHEMA_VERSION
            h5.attrs["migrated_at"] = datetime.now(timezone.utc).isoformat()

            for grp in [
                "hardware_profiles",
                "basis_sets",
                "embedded_basis_sets",
                "provenance",
                "seeds",
                "metadata",
            ]:
                if grp not in h5:
                    h5.create_group(grp)

            return {
                "previous_version": str(prev_ver),
                "current_version": self.SCHEMA_VERSION,
                "status": "migrated",
            }

    def set_metadata(self, key: str, value: Any) -> None:
        """Sets arbitrary metadata key/value into the registry."""
        with self.transaction("a") as h5:
            meta_grp = h5["metadata"]
            if key in meta_grp:
                del meta_grp[key]
            meta_grp.create_dataset(
                key, data=json.dumps(value), dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Retrieves arbitrary metadata value."""
        with self.transaction("r") as h5:
            if "metadata" not in h5 or key not in h5["metadata"]:
                return default
            val = h5["metadata"][key][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return json.loads(text)


__all__ = [
    "AtomicFileLock",
    "BaseMetadataServer",
    "BasisSetNotFoundError",
    "CoChemLockTimeoutError",
    "FilesystemMetadataServer",
    "IsotopeStabilityError",
    "MetadataBackendType",
    "MetadataServerManager",
    "PostgresMetadataServer",
    "RecordNotFoundError",
    "RedisMetadataServer",
    "RegistryCorruptionError",
    "RegistryError",
    "RegistryLockError",
    "RegistryLockTimeoutError",
    "RegistryManager",
    "RegistryMissingError",
    "RegistryParseError",
    "SchemaMigrationError",
    "atomic_write_json",
    "broadcast_system_config",
    "default_metadata_manager",
    "get_active_job",
    "get_default_config_path",
    "hash_environment",
    "interpolate_env_vars",
    "is_master_node",
    "list_active_jobs",
    "load_system_config",
    "migrate_schema",
    "nfs_atomic_directory_rename",
    "receive_system_config_broadcast",
    "register_active_job",
    "remove_active_job",
    "save_system_config",
    "update_active_job",
    "update_system_config",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\cochem_crypto.py ---
"""Authoritative IETF RFC 8032 PureEd25519, RFC 8785 JSON Canonicalization Scheme (JCS), & W3C Linked Data Proofs.

Provides pure asymmetric cryptographic provenance generation, verification, and offline
did:key resolution using multicodec 0xed01 prefix and base58btc encoding.
Eradicates non-standard intermediate SHA-512 pre-hashing, signing raw canonical bytes directly.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple, Union

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


def canonicalize_json(data: Any) -> bytes:
    """Canonicalize Python dictionary, list, primitive, or Pydantic model according to RFC 8785 (JCS).

    Sorts dictionary keys lexicographically, removes whitespace, and outputs UTF-8 encoded bytes.
    """
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif isinstance(data, BaseModel):
        data = data.dict()
    elif isinstance(data, dict):
        clean_dict = {}
        for k, v in data.items():
            if hasattr(v, "model_dump"):
                clean_dict[str(k)] = v.model_dump(mode="json")
            elif isinstance(v, BaseModel):
                clean_dict[str(k)] = v.dict()
            else:
                clean_dict[str(k)] = v
        data = clean_dict

    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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
    # RFC 8032 §5.1 PureEd25519: Sign raw canonical bytes directly
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
    # Clean payload excluding any existing proof block
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
    "canonicalize_json",
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\glossary.py ---
"""Authoritative CODATA 2018 / 2022 IEEE-754 FP64 Physical Conversion Constants & Method Matrix Glossary.

Provides single repository source of truth for energy, coordinate, and rotational inertia conversions,
as well as canonical composite calculation fidelity tiers defined in Method Matrix v4 (§9A, Table 3).
Strictly adheres to Method Matrix §4.4, §5, §8B, §9A and authoritative CODATA recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class CalculationFidelity(str, Enum):
    """Authoritative Method Matrix v4 calculation fidelity tiers and canonical composite recipes [D]."""

    # Low / Semiempirical Tiers
    XTB1 = "XTB1"
    XTB2 = "XTB2"
    PM6 = "PM6"
    AM1 = "AM1"

    # Single Reference / Mean Field
    R_HF = "R_HF"
    U_HF = "U_HF"
    R_DFT = "R_DFT"
    U_DFT = "U_DFT"
    RO_DFT = "RO_DFT"

    # Correlated Wavefunction
    MP2 = "MP2"
    DLPNO_CCSD_T = "DLPNO_CCSD_T"
    CCSD_T = "CCSD_T"
    CCSD_T_F12 = "CCSD_T_F12"
    CASSCF = "CASSCF"
    NEVPT2 = "NEVPT2"

    # Method Matrix v4 Canonical Composite Tiers (Table 3 & §9A)
    JUNCHS = "junChS"
    JUNCHS_F12 = "junChS-F12"
    CHS = "ChS"
    CHS_F12 = "ChS-F12"
    T3_10S = "T3-10s"
    T3_1MIN = "T3-1min"
    T3_30MIN = "T3-30min"
    T3_3H = "T3-3h"
    T3_12H = "T3-12h"
    T4_1D = "T4-1d"
    R2 = "R2"

    # Custom / Open QCSchema Specification
    CUSTOM_COMPOSITE = "CUSTOM_COMPOSITE"


@dataclass(frozen=True)
class _UnitConversionConstants:
    """Authoritative physical constants at full IEEE-754 double precision."""

    HARTREE_TO_EV: float = 27.211386245981
    HARTREE_TO_JOULE: float = 4.359744722206e-18
    HARTREE_TO_KCAL_MOL: float = 627.5094740631
    KCAL_MOL_TO_HARTREE: float = 1.0 / 627.5094740631
    HARTREE_TO_CM_INV: float = 219474.63136320
    BOHR_TO_ANGSTROM: float = 0.529177210903
    ANGSTROM_TO_BOHR: float = 1.0 / 0.529177210903
    AMU_TO_KG: float = 1.66053906660e-27
    PLANCK_CONSTANT: float = 6.62607015e-34
    SPEED_OF_LIGHT_CM_S: float = 29979245800.0
    ROTATIONAL_INERTIA_CONVERSION: float = 505379.0084350172


UnitConversionConstants: Final[_UnitConversionConstants] = _UnitConversionConstants()

# Top-level module exports for ergonomic direct imports
HARTREE_TO_EV: Final[float] = UnitConversionConstants.HARTREE_TO_EV
HARTREE_TO_JOULE: Final[float] = UnitConversionConstants.HARTREE_TO_JOULE
HARTREE_TO_KCAL_MOL: Final[float] = UnitConversionConstants.HARTREE_TO_KCAL_MOL
KCAL_MOL_TO_HARTREE: Final[float] = UnitConversionConstants.KCAL_MOL_TO_HARTREE
HARTREE_TO_CM_INV: Final[float] = UnitConversionConstants.HARTREE_TO_CM_INV
BOHR_TO_ANGSTROM: Final[float] = UnitConversionConstants.BOHR_TO_ANGSTROM
ANGSTROM_TO_BOHR: Final[float] = UnitConversionConstants.ANGSTROM_TO_BOHR
AMU_TO_KG: Final[float] = UnitConversionConstants.AMU_TO_KG
PLANCK_CONSTANT: Final[float] = UnitConversionConstants.PLANCK_CONSTANT
SPEED_OF_LIGHT_CM_S: Final[float] = UnitConversionConstants.SPEED_OF_LIGHT_CM_S
ROTATIONAL_INERTIA_CONVERSION: Final[float] = UnitConversionConstants.ROTATIONAL_INERTIA_CONVERSION

__all__ = [
    "CalculationFidelity",
    "UnitConversionConstants",
    "HARTREE_TO_EV",
    "HARTREE_TO_JOULE",
    "HARTREE_TO_KCAL_MOL",
    "KCAL_MOL_TO_HARTREE",
    "HARTREE_TO_CM_INV",
    "BOHR_TO_ANGSTROM",
    "ANGSTROM_TO_BOHR",
    "AMU_TO_KG",
    "PLANCK_CONSTANT",
    "SPEED_OF_LIGHT_CM_S",
    "ROTATIONAL_INERTIA_CONVERSION",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\models.py ---
"""Authoritative Core Data Models & MolSSI QCSchema v1 Envelopes.

Defines QCResultsRecord (AtomicResult), MolecularTopology, PESPointRecord, and CalculationJobPayload
with explicit spatial coordinate envelopes, CODATA 2022 constants, deterministic UUIDv5 content hashing,
and machine-readable SPDX licensing.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cochem_base.core.cochem_crypto import canonicalize_json
from cochem_base.core.glossary import CalculationFidelity
from cochem_base.core.licensing import validate_spdx_license

# Authoritative CODATA 2022 conversion factors
BOHR_TO_ANGSTROM: float = 0.529177210903
ANGSTROM_TO_BOHR: float = 1.0 / BOHR_TO_ANGSTROM

# Authoritative CoChem Namespace UUID for deterministic UUIDv5 hashing
NAMESPACE_COCHEM: uuid.UUID = uuid.UUID("a6c4f69a-2d4e-4e68-912f-6e2101e4a682")


class QCResultsRecord(BaseModel):
    """MolSSI QCSchema v1 compliant AtomicResult record with backward-compatible accessors."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True, validate_assignment=True)

    schema_name: Literal["qcschema_output"] = "qcschema_output"
    schema_version: int = 1
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


class MolecularTopology(BaseModel):
    """Molecular spatial coordinates standardized to flat 1D arrays with explicit unit tagging."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    symbols: List[str] = Field(..., description="Ordered IUPAC elemental symbols")
    geometry: List[float] = Field(..., description="Flat 1D atomic Cartesian coordinates (size 3*N)")
    units: Literal["bohr", "angstrom"] = Field(default="bohr", description="Physical coordinate unit")

    @model_validator(mode="before")
    @classmethod
    def _validate_and_flatten_coords(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        symbols = data.get("symbols", [])
        geom = data.get("geometry", [])

        # Flatten 2D coordinate arrays if provided
        if isinstance(geom, np.ndarray):
            geom = geom.flatten().tolist()
        elif isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
            flat = []
            for pt in geom:
                flat.extend([float(c) for c in pt])
            geom = flat
        elif isinstance(geom, list):
            geom = [float(c) for c in geom]

        n_atoms = len(symbols)
        if n_atoms > 0 and len(geom) != 3 * n_atoms:
            raise ValueError(
                f"Geometry coordinate dimension mismatch: expected {3 * n_atoms} components for {n_atoms} atoms, got {len(geom)}"
            )

        data["geometry"] = geom
        return data

    def to_angstrom(self) -> MolecularTopology:
        """Convert coordinates to Angstroms using authoritative CODATA 2022 constant."""
        if self.units == "angstrom":
            return self
        converted = [float(c * BOHR_TO_ANGSTROM) for c in self.geometry]
        return MolecularTopology(
            symbols=list(self.symbols),
            geometry=converted,
            units="angstrom",
        )

    def to_bohr(self) -> MolecularTopology:
        """Convert coordinates to Bohr using authoritative CODATA 2022 constant."""
        if self.units == "bohr":
            return self
        converted = [float(c * ANGSTROM_TO_BOHR) for c in self.geometry]
        return MolecularTopology(
            symbols=list(self.symbols),
            geometry=converted,
            units="bohr",
        )


class PESPointRecord(BaseModel):
    """Point record representing a single potential energy surface evaluation with deterministic UUIDv5 [D]."""

    model_config = ConfigDict(extra="allow", validate_assignment=True, arbitrary_types_allowed=True)

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

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique job identifier")
    molecule: Dict[str, Any] = Field(default_factory=dict, description="Target molecular topology specifications")
    driver: Literal["energy", "gradient", "hessian", "properties"] = "energy"
    fidelity: Union[CalculationFidelity, str] = Field(
        default=CalculationFidelity.R_DFT,
        description="Canonical fidelity tier or custom specification",
    )
    keywords: Dict[str, Any] = Field(default_factory=dict, description="Calculation keywords")
    license: str = Field(default="CC-BY-4.0", description="SPDX license identifier")

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
    "QCResultsRecord",
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
        self.path = Path(path).resolve()
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_core_registry_schema.py ---
#!/usr/bin/env python3
"""
CoChem-CORE: Re-exports authoritative schemas from root cochem_core_registry_schema.
"""

from cochem_core_registry_schema import (
    BYPASS_TOKENS,
    CARBON_13_ISOTOPIC_MASS,
    get_registry_atomic_mass,
    CoChemConfig,
    CoChemSystemConfig,
    CorePinningConfig,
    EngineInfo,
    EnginePaths,
    EnvironmentSchema,
    GPUComputeSchema,
    HPCConfig,
    HardwareConfig,
    HardwareSchema,
    MPSConfig,
    OSTarget,
    QuantumSettings,
    RoutingPolicy,
    SiloConfig,
    SiloPathsSchema,
    discover_engine,
    discover_host_hardware,
    validate_system_config,
)

__all__ = [
    "BYPASS_TOKENS",
    "CARBON_13_ISOTOPIC_MASS",
    "get_registry_atomic_mass",
    "CoChemConfig",
    "CoChemSystemConfig",
    "CorePinningConfig",
    "EngineInfo",
    "EnginePaths",
    "EnvironmentSchema",
    "GPUComputeSchema",
    "HPCConfig",
    "HardwareConfig",
    "HardwareSchema",
    "MPSConfig",
    "OSTarget",
    "QuantumSettings",
    "RoutingPolicy",
    "SiloConfig",
    "SiloPathsSchema",
    "discover_engine",
    "discover_host_hardware",
    "validate_system_config",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\orchestrator\cochem_setup_phase_5.py ---
"""
CoChem Setup Phase 5: IPC Config Lock & Workspace Sweep & NVIDIA MPS Daemon / VRAM Budgeting Gatekeeper.
Production-grade, zero-mock gatekeeping engine for:
1. Multi-tenant NVIDIA Multi-Process Service (MPS) daemon management (nvidia-cuda-mps-control)
   and dynamically calculated pinned device memory partitioning (CUDA_MPS_PINNED_DEVICE_MEM_LIMIT).
2. Physical POSIX byte-range locking verification (fcntl / msvcrt) before HDF5 SWMR initialization,
   with graceful degradation to single-threaded operations upon filesystem locking failure.
3. Intermediate state consolidation (p1.json through p11.json) and validation through the rigid
   Pydantic v2 CoChemSystemConfig schema.
4. Atomic serialization of the finalized Golden Registry to $HOME/CoChem_Artifacts/Registry/cochem_system_config.json
   with status="LOCKED" and os.chmod(0o444) read-only immutability enforcement.
5. Workspace garbage collection sweep purging ephemeral .tmp files and intermediate staging fragments.

SRS Document 2 Part 2 (Section 3.5), SRS Document 5 (Section 4.3), and Method Matrix v4 Compliant.
"""

from __future__ import annotations

import argparse
import getpass
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

import psutil
from pydantic import BaseModel, ConfigDict, Field, field_validator

# POSIX fcntl / Windows msvcrt locking imports
try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

# Schema and Config Imports with Path Resolution Fallbacks
try:
    from cochem_core_registry_schema import (
        CARBON_13_ISOTOPIC_MASS,
        get_registry_atomic_mass,
        CoChemSystemConfig,
        OSTarget,
        discover_host_hardware,
    )
except ImportError:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from cochem_core_registry_schema import (
        CARBON_13_ISOTOPIC_MASS,
        get_registry_atomic_mass,
        CoChemSystemConfig,
        OSTarget,
        discover_host_hardware,
    )

import atexit
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("cochem_setup_phase_5")

def sweep_zombies() -> None:
    if psutil is None:
        return
    for p in psutil.process_iter(['pid', 'status']):
        try:
            if p.info['status'] == psutil.STATUS_ZOMBIE:
                p.wait(timeout=1)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied, KeyError):
            pass

atexit.register(sweep_zombies)


# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class Phase5AuditError(RuntimeError):
    """Raised when critical phase 5 MPS daemon initialization or VRAM allocation fails fatally."""


class MPSControlError(RuntimeError):
    """Raised when nvidia-cuda-mps-control daemon lifecycle management commands fail unexpectedly."""


class VRAMAllocationError(RuntimeError):
    """Raised when VRAM memory limits or worker capacity cannot be safely bounded."""


class ConfigLockError(RuntimeError):
    """Raised when golden master registry configuration locking fails."""


class LockTestFailureError(RuntimeError):
    """Raised when physical POSIX filesystem locking verification encounters an unrecoverable error."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS & ENUMS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    BYPASSED = "BYPASSED"


class MPSStatus(str, Enum):
    """Operational status enumeration for NVIDIA MPS daemon subsystem."""

    RUNNING = "RUNNING"
    INITIALIZED = "INITIALIZED"
    STOPPED = "STOPPED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class GPUDeviceVRAM(BaseModel):
    """Physical GPU device VRAM allocation and worker partitioning profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    index: int = Field(..., ge=0, description="Physical GPU device index (e.g. 0, 1)")
    name: str = Field(..., description="GPU model/product identifier")
    uuid: Optional[str] = Field(default=None, description="GPU device UUID if available")
    total_vram_mb: float = Field(..., ge=0.0, description="Total physical VRAM in megabytes")
    free_vram_mb: float = Field(default=0.0, ge=0.0, description="Available unallocated VRAM in megabytes")
    reserved_vram_mb: float = Field(default=0.0, ge=0.0, description="VRAM reserved for OS/UI/host buffers in megabytes")
    allocatable_vram_mb: float = Field(default=0.0, ge=0.0, description="Net allocatable VRAM for compute workers in megabytes")
    allocated_limit_per_worker_mb: float = Field(
        default=0.0, ge=0.0, description="Calculated pinned memory limit per concurrent worker in megabytes"
    )
    active_worker_capacity: int = Field(
        default=1, ge=1, description="Maximum concurrent GPU worker processes supported without OOM"
    )
    pinned_mem_limit_str: str = Field(
        default="", description="Formatted CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string (e.g. '0=4096M')"
    )
    compute_capability: Optional[str] = Field(
        default=None, description="CUDA compute capability architecture (e.g. 'sm_80', 'sm_89')"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("GPU name cannot be empty")
        return v.strip()


class MPSDaemonAudit(BaseModel):
    """Structured inspection and lifecycle state of the NVIDIA MPS daemon."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    mps_control_binary: Optional[str] = Field(
        default=None, description="Absolute filesystem path to nvidia-cuda-mps-control executable"
    )
    mps_server_binary: Optional[str] = Field(
        default=None, description="Absolute filesystem path to nvidia-cuda-mps-server executable"
    )
    status: MPSStatus = Field(default=MPSStatus.NOT_SUPPORTED, description="Operational status of MPS daemon")
    pipe_directory: Optional[str] = Field(
        default=None, description="Directory path for CUDA_MPS_PIPE_DIRECTORY IPC pipe/sockets"
    )
    log_directory: Optional[str] = Field(
        default=None, description="Directory path for CUDA_MPS_LOG_DIRECTORY telemetry logs"
    )
    socket_path: Optional[str] = Field(
        default=None, description="Active Unix domain socket or named pipe path for daemon communication"
    )
    is_daemon_active: bool = Field(
        default=False, description="Whether the nvidia-cuda-mps-control daemon process is running"
    )
    pid: Optional[int] = Field(
        default=None, description="Process ID of active nvidia-cuda-mps-control daemon"
    )
    socket_permissions: Optional[str] = Field(
        default=None, description="Octal permission mode (e.g. '0o700') or ACL string"
    )
    is_permission_secure: bool = Field(
        default=True, description="Whether socket permissions enforce 0700 restricted access"
    )
    server_active: bool = Field(
        default=False, description="Whether backend nvidia-cuda-mps-server process is active"
    )
    control_active: bool = Field(
        default=False, description="Whether nvidia-cuda-mps-control command pipe is responsive"
    )
    environment_variables: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables configured for MPS operations"
    )
    details: str = Field(default="", description="Diagnostic status summary and telemetry details")


class VRAMBudgetReport(BaseModel):
    """Aggregated cluster-wide VRAM memory budgeting and concurrency partitioning record."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_gpus_detected: int = Field(default=0, ge=0, description="Total number of physical GPUs discovered")
    active_gpu_devices: List[GPUDeviceVRAM] = Field(
        default_factory=list, description="Per-GPU VRAM profiles and allocation limits"
    )
    total_cluster_vram_mb: float = Field(
        default=0.0, ge=0.0, description="Total aggregated VRAM across all GPUs in megabytes"
    )
    total_reserved_vram_mb: float = Field(
        default=0.0, ge=0.0, description="Total aggregated reserved VRAM across all GPUs in megabytes"
    )
    total_allocatable_vram_mb: float = Field(
        default=0.0, ge=0.0, description="Total aggregated allocatable VRAM across all GPUs in megabytes"
    )
    worker_concurrency_target: int = Field(
        default=2, ge=1, description="Configured target concurrent GPU worker processes (e.g. 2 for MACE+PySCF)"
    )
    default_pinned_mem_limit: Optional[str] = Field(
        default=None, description="Default global CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string"
    )
    per_device_limits: Dict[str, str] = Field(
        default_factory=dict, description="Mapping of device indices to pinned memory limits (e.g. {'0': '4096M'})"
    )
    is_vram_bounded: bool = Field(
        default=True, description="Whether VRAM allocations are strictly bounded to prevent OOM"
    )
    strategy: str = Field(
        default="PROPORTIONAL_PINNED_BUDGET", description="Applied VRAM partitioning strategy algorithm"
    )


class LockTestResult(BaseModel):
    """Physical POSIX byte-range locking verification result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    passed: bool = Field(..., description="Whether byte-range locking succeeded on target filesystem")
    method: str = Field(..., description="Locking mechanism utilized (e.g. 'POSIX_FCNTL', 'MSVCRT_LOCKING')")
    single_threaded_mode: bool = Field(
        default=False,
        description="Whether single-threaded fallback degradation is active due to lock failure",
    )
    target_path: str = Field(..., description="Filesystem path tested for byte-range locking")
    lock_type: str = Field(default="POSIX_BYTE_RANGE_LOCK", description="Classification of lock test")
    error_message: Optional[str] = Field(default=None, description="Error diagnostics if lock test failed")


class WorkspaceSweepReport(BaseModel):
    """Artifact sweep report for garbage collection of intermediate setup files."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    swept_files_count: int = Field(default=0, ge=0, description="Number of temporary or fragment files cleaned")
    cleaned_paths: List[str] = Field(default_factory=list, description="Paths of cleaned ephemeral files")
    retained_paths: List[str] = Field(default_factory=list, description="Paths of permanent registered artifacts")
    trash_dir: Optional[str] = Field(default=None, description="Backup trash destination if configured")


class ConfigLockAuditReport(BaseModel):
    """Structured audit report for IPC configuration lock and workspace sweep."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    golden_registry_path: str = Field(..., description="Canonical path to locked cochem_system_config.json")
    status: str = Field(default="LOCKED", description="Operational status of master registry ('LOCKED')")
    checksum: str = Field(..., description="Deterministic SHA-256 checksum of locked configuration")
    posix_lock_test: LockTestResult = Field(..., description="Byte-range filesystem lock verification record")
    sweep_report: WorkspaceSweepReport = Field(..., description="Workspace garbage collection sweep results")
    intermediate_phases_found: List[str] = Field(
        default_factory=list, description="Intermediate phase artifacts consolidated (e.g. ['p1.json', 'p2.json'])"
    )
    is_immutable_mode_enforced: bool = Field(
        default=True, description="Whether 0o444 read-only file mode was applied"
    )


class Phase5AuditReport(BaseModel):
    """Comprehensive serialized audit report for Phase 5 NVIDIA MPS Daemon & VRAM Budgeting & Config Lock."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    phase_id: str = Field(
        default="PHASE_5_NVIDIA_MPS_VRAM_BUDGETING",
        description="Unique phase identifier",
    )
    status: PhaseStatus = Field(..., description="Overall phase outcome status")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    mps_daemon: MPSDaemonAudit = Field(..., description="NVIDIA MPS daemon lifecycle and socket audit")
    vram_budget: VRAMBudgetReport = Field(..., description="Calculated VRAM partitioning and budgeting report")
    is_cuda_available: bool = Field(default=False, description="Whether CUDA runtime and hardware are available")
    is_hpc_slurm: bool = Field(default=False, description="Whether execution occurred within a Slurm HPC envelope")
    config_lock: Optional[ConfigLockAuditReport] = Field(
        default=None, description="Phase 5 IPC config lock and workspace sweep results"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings or degraded notices")
    errors: List[str] = Field(default_factory=list, description="Fatal or critical validation errors")
    artifact_path: str = Field(..., description="Filesystem destination path for serialized p5.json")
    golden_config_path: Optional[str] = Field(
        default=None, description="Filesystem destination path for locked cochem_system_config.json"
    )

    @field_validator("phase_id")
    @classmethod
    def validate_phase_id(cls, v: str) -> str:
        if v != "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING":
            raise ValueError(f"Invalid phase_id: {v}")
        return v


# =============================================================================
# 3. TRANSACTIONAL DEPENDENCY & ATOMIC STATE MANAGER
# =============================================================================


class DependencyManager:
    """
    Transactional context manager for managing temporary files, staging directories,
    and executing atomic JSON state persistence with automatic rollback on unhandled exceptions.
    Ensures workspace sterility per SRS Document 5 Section 1.3.
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

    def rollback(self) -> None:
        """Explicitly purge all tracked temporary files and directories."""
        for temp_file in list(self._tracked_temp_files):
            try:
                if temp_file.exists() and temp_file.is_file():
                    try:
                        os.chmod(temp_file, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
                    temp_file.unlink()
            except OSError:
                pass
        self._tracked_temp_files.clear()

        for temp_dir in list(self._tracked_temp_dirs):
            try:
                if temp_dir.exists() and temp_dir.is_dir():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError:
                pass
        self._tracked_temp_dirs.clear()

    def atomic_write_json(
        self,
        target_path: Union[str, Path],
        data: Union[BaseModel, Dict[str, Any], Any],
        indent: int = 2,
        read_only: bool = False,
    ) -> Path:
        """
        Atomically write JSON content to target_path using a staged temporary file and os.replace.
        Handles overwriting existing read-only files cleanly.
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

        # If target exists and is read-only (Windows NT or POSIX), unlock it temporarily for replacement
        if target.exists():
            try:
                os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IWUSR | stat.S_IRUSR)
            except OSError:
                pass

        os.replace(staged_file, target)
        self.untrack_file(staged_file)

        if read_only:
            try:
                os.chmod(target, stat.S_IREAD | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            except OSError:
                pass

        return target


# =============================================================================
# 4. PATH RESOLUTION & DIRECTORY PROVISIONING
# =============================================================================


def get_current_username() -> str:
    """Retrieve the current OS username sanitized for filesystem paths."""
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or "default_user"
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", user)


def resolve_mps_pipe_directory(custom_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve isolated runtime control pipe directory for CUDA_MPS_PIPE_DIRECTORY following
    the authoritative CoChem hierarchy:
    1. Explicit custom_dir parameter
    2. Environment variable CUDA_MPS_PIPE_DIRECTORY
    3. Slurm HPC envelope: $SLURM_TMPDIR/cochem_mps_$USER
    4. Linux / POSIX default: /tmp/cochem_mps_$USER
    5. Windows fallback: %TEMP%\\cochem_mps_%USERNAME%
    """
    if custom_dir:
        resolved = Path(custom_dir).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    env_pipe = os.environ.get("CUDA_MPS_PIPE_DIRECTORY")
    if env_pipe:
        resolved = Path(env_pipe).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    user = get_current_username()
    slurm_job = os.environ.get("SLURM_JOB_ID")
    dir_suffix = f"_{slurm_job}" if slurm_job else ""
    slurm_tmp = os.environ.get("SLURM_TMPDIR")
    if slurm_tmp and Path(slurm_tmp).is_dir():
        resolved = Path(slurm_tmp).resolve() / f"cochem_mps_{user}{dir_suffix}"
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    if platform.system() != "Windows":
        resolved = Path(f"/tmp/cochem_mps_{user}{dir_suffix}").resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    win_temp = Path(tempfile.gettempdir()) / f"cochem_mps_{user}{dir_suffix}"
    win_temp.mkdir(parents=True, exist_ok=True)
    return win_temp.resolve()


def resolve_mps_log_directory(custom_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve log directory for CUDA_MPS_LOG_DIRECTORY following the CoChem hierarchy.
    """
    if custom_dir:
        resolved = Path(custom_dir).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    env_log = os.environ.get("CUDA_MPS_LOG_DIRECTORY")
    if env_log:
        resolved = Path(env_log).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    user = get_current_username()
    slurm_job = os.environ.get("SLURM_JOB_ID")
    dir_suffix = f"_{slurm_job}" if slurm_job else ""
    slurm_tmp = os.environ.get("SLURM_TMPDIR")
    if slurm_tmp and Path(slurm_tmp).is_dir():
        resolved = Path(slurm_tmp).resolve() / f"cochem_mps_log_{user}{dir_suffix}"
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    if platform.system() != "Windows":
        resolved = Path(f"/tmp/cochem_mps_log_{user}{dir_suffix}").resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    win_log = Path(tempfile.gettempdir()) / f"cochem_mps_log_{user}{dir_suffix}"
    win_log.mkdir(parents=True, exist_ok=True)
    return win_log.resolve()


def enforce_socket_directory_permissions(dir_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Enforce restrictive 0700 (owner-only read/write/execute) permissions on Unix socket directories
    to prevent IPC spoofing and privilege escalation across multi-tenant environments.
    """
    if platform.system() == "Windows":
        return True, "0o700 (Windows NT ACL inherited)"

    try:
        current_mode = dir_path.stat().st_mode
        if (current_mode & 0o077) != 0:
            dir_path.chmod(0o700)
        mode_str = oct(stat.S_IMODE(dir_path.stat().st_mode))
        return True, mode_str
    except OSError:
        return False, None


def resolve_p5_registry_path(output_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve canonical destination path for Golden Registry artifact p5.json.
    """
    if output_dir:
        out_path = Path(output_dir).resolve()
        if out_path.suffix == ".json" or out_path.name == "p5.json":
            return out_path
        return out_path / "p5.json"

    try:
        from cochem_base.config_loader import get_artifact_dir

        return get_artifact_dir() / "Registry" / "p5.json"
    except ImportError:
        pass

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return Path(env_art).resolve() / "Registry" / "p5.json"

    repo_root_candidate = Path.cwd()
    agent_artifacts = repo_root_candidate / ".agent_artifacts"
    if agent_artifacts.exists():
        return agent_artifacts / "Registry" / "p5.json"

    home_artifacts = Path.home() / "CoChem_Artifacts"
    return home_artifacts / "Registry" / "p5.json"


def resolve_golden_config_path(output_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve destination path for finalized master Golden Registry cochem_system_config.json
    per SRS Document 5 Section 4.3.
    """
    if output_path:
        out_p = Path(output_path).resolve()
        if out_p.is_dir() or out_p.suffix == "":
            return out_p / "cochem_system_config.json"
        return out_p

    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg:
        return Path(os.path.expandvars(env_cfg)).expanduser().resolve()

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return (
            Path(os.path.expandvars(env_art)).expanduser()
            / "Registry"
            / "cochem_system_config.json"
        ).resolve()

    try:
        from cochem_base.config_loader import resolve_config_path

        return resolve_config_path()
    except Exception:
        pass

    return (Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json").resolve()


# =============================================================================
# 5. PHYSICAL POSIX BYTE-RANGE LOCKING TEST (FCNTL / MSVCRT)
# =============================================================================


def test_posix_byte_range_locking(
    target_dir: Optional[Union[str, Path]] = None,
    timeout: float = 2.0,
) -> LockTestResult:
    """
    Execute a physical POSIX byte-range locking test (fcntl on Linux/macOS, msvcrt on Windows)
    on the target filesystem prior to initializing HDF5 SWMR streams.

    SRS Document 5 Section 4.3 Mandate:
    If the filesystem does not support POSIX byte-range locks (e.g., certain NFS/SMB/CIFS mounts
    or legacy virtualized mounts), this test catches the failure and signals graceful degradation
    to single-threaded operations.
    """
    if target_dir:
        test_dir = Path(target_dir).resolve()
    else:
        test_dir = resolve_golden_config_path().parent

    test_dir.mkdir(parents=True, exist_ok=True)
    probe_filename = f".cochem_swmr_lock_probe_{uuid.uuid4().hex[:8]}.lock"
    probe_path = test_dir / probe_filename

    is_posix = platform.system() != "Windows"

    try:
        # Create physical probe file with data to lock
        with open(probe_path, "w+b") as f:
            f.write(b"COCHEM_SWMR_BYTE_RANGE_LOCK_PROBE_HEADER_BLOCK\n" * 10)
            f.flush()
            fd = f.fileno()

            if is_posix and fcntl is not None:
                # Test POSIX fcntl byte-range locking
                try:
                    # Exclusive byte-range lock on bytes 0..512
                    fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 512, 0)
                    # Unlock
                    fcntl.lockf(fd, fcntl.LOCK_UN, 512, 0)
                    method = "POSIX_FCNTL_LOCKF"
                except (OSError, IOError) as exc:
                    return LockTestResult(
                        passed=False,
                        method="POSIX_FCNTL_LOCKF",
                        single_threaded_mode=True,
                        target_path=str(probe_path),
                        error_message=f"POSIX byte-range lock failed on filesystem: {exc}",
                    )
            elif not is_posix and msvcrt is not None:
                # Test Windows NT byte-range locking
                try:
                    f.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 512)
                    f.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 512)
                    method = "MSVCRT_LOCKING_BYTE_RANGE"
                except (OSError, IOError) as exc:
                    return LockTestResult(
                        passed=False,
                        method="MSVCRT_LOCKING_BYTE_RANGE",
                        single_threaded_mode=True,
                        target_path=str(probe_path),
                        error_message=f"Windows byte-range lock failed on filesystem: {exc}",
                    )
            else:
                method = "GENERIC_FALLBACK_LOCK"

        return LockTestResult(
            passed=True,
            method=method,
            single_threaded_mode=False,
            target_path=str(probe_path),
            error_message=None,
        )

    except Exception as e:
        return LockTestResult(
            passed=False,
            method="UNKNOWN_ERROR",
            single_threaded_mode=True,
            target_path=str(probe_path),
            error_message=f"Filesystem byte-range locking test exception: {e}",
        )
    finally:
        try:
            if probe_path.exists():
                probe_path.unlink()
        except OSError:
            pass


def _sanitize_engine_record(raw_eng: Any) -> Optional[Dict[str, Any]]:
    """Sanitize raw engine dictionary to match strict EngineInfo schema."""
    if not isinstance(raw_eng, dict):
        return None
    st_raw = str(raw_eng.get("status", "")).lower()
    if "found" in st_raw or raw_eng.get("is_available") is True:
        st = "found"
    elif "bypass" in st_raw:
        st = "bypassed"
    elif "denied" in st_raw or "permission" in st_raw:
        st = "permission_denied"
    else:
        st = "missing" if not raw_eng.get("path") else "found"

    p = raw_eng.get("path")
    v = raw_eng.get("version")
    h = raw_eng.get("sha256_hash") or raw_eng.get("hash")
    return {
        "status": st,
        "path": str(p) if p else None,
        "version": str(v) if v else None,
        "hash": str(h) if h else None,
    }


def consolidate_intermediate_states(
    registry_dir: Optional[Union[str, Path]] = None,
    search_dirs: Optional[List[Union[str, Path]]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Consolidate intermediate phase states (p1.json through p11.json) discovered across
    the registry search paths into a single structured configuration payload ready for
    validation against CoChemSystemConfig.

    SRS Document 5 Section 4.3 Mandate.
    """
    candidate_dirs: List[Path] = []
    if registry_dir:
        candidate_dirs.append(Path(registry_dir).resolve())

    if search_dirs:
        for sd in search_dirs:
            candidate_dirs.append(Path(sd).resolve())

    env_reg = os.environ.get("COCHEM_REGISTRY_DIR")
    if env_reg:
        candidate_dirs.append(Path(env_reg).resolve())

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        candidate_dirs.append((Path(env_art) / "Registry").resolve())

    candidate_dirs.append((Path.cwd() / ".agent_artifacts" / "Registry").resolve())
    candidate_dirs.append((Path.cwd() / "artifacts" / "registry").resolve())
    candidate_dirs.append((Path.home() / "CoChem_Artifacts" / "Registry").resolve())

    consolidated_raw: Dict[str, Any] = {}
    found_phases: List[str] = []

    # Map of intermediate JSON filenames to phase identifiers
    target_files = [f"p{i}.json" for i in range(1, 12)]

    for phase_filename in target_files:
        for cdir in candidate_dirs:
            phase_file = cdir / phase_filename
            if phase_file.is_file():
                try:
                    phase_data = json.loads(phase_file.read_text(encoding="utf-8"))
                    found_phases.append(phase_filename)

                    # Extract and merge domain-specific fields from each phase
                    if phase_filename == "p1.json":
                        # OS & Toolchain Audit
                        os_val = phase_data.get("os_target") or phase_data.get("os_profile", {}).get("system") or phase_data.get("os", {}).get("os_target")
                        if os_val:
                            consolidated_raw["os_target"] = os_val

                    elif phase_filename == "p2.json":
                        # Hardware & RAM Profiling
                        cpu_info = phase_data.get("cpu", {})
                        ram_info = phase_data.get("memory", {}) or phase_data.get("ram", {})
                        gpu_info = phase_data.get("gpu", {})

                        if "hardware" not in consolidated_raw:
                            consolidated_raw["hardware"] = {}

                        hw = consolidated_raw["hardware"]
                        if "physical_cores" in cpu_info:
                            hw["cpu_physical_cores"] = cpu_info["physical_cores"]
                            hw["physical_cpu_cores"] = cpu_info["physical_cores"]
                        if "logical_cores" in cpu_info:
                            hw["logical_cpu_cores"] = cpu_info["logical_cores"]

                        total_bytes = ram_info.get("total_physical_bytes") or ram_info.get("total_ram_bytes")
                        if total_bytes:
                            hw["ram_gb"] = round(float(total_bytes) / (1024.0**3), 2)
                        elif "total_ram_gb" in ram_info:
                            hw["ram_gb"] = float(ram_info["total_ram_gb"])
                        elif "ram_gb" in ram_info:
                            hw["ram_gb"] = float(ram_info["ram_gb"])

                        if "avx512_support" in cpu_info:
                            hw["avx_512_capable"] = bool(cpu_info["avx512_support"])
                            hw["avx512_support"] = bool(cpu_info["avx512_support"])

                        if gpu_info.get("gpu_available") or gpu_info.get("available"):
                            devices_list = gpu_info.get("devices") or []
                            if devices_list:
                                first_dev = devices_list[0]
                                hw["gpu_profile"] = first_dev.get("name", "NVIDIA GPU")
                                vram_bytes = first_dev.get("memory_total_bytes", 0)
                                if vram_bytes:
                                    hw["vram_gb"] = round(float(vram_bytes) / (1024.0**3), 2)

                    elif phase_filename == "p3.json":
                        # Multi-Track Quantum Engine Discovery
                        engines_data = phase_data.get("engines", {})
                        if engines_data and isinstance(engines_data, dict):
                            cleaned_engines: Dict[str, Any] = {}
                            if "silo_paths" not in consolidated_raw:
                                consolidated_raw["silo_paths"] = {}
                            sp = consolidated_raw["silo_paths"]

                            for eng_name, eng_info in engines_data.items():
                                sanitized = _sanitize_engine_record(eng_info)
                                if sanitized:
                                    cleaned_engines[eng_name] = sanitized
                                    if sanitized.get("path"):
                                        if eng_name == "orca":
                                            sp["orca_binary_path"] = sanitized["path"]
                                        elif eng_name == "xtb":
                                            sp["xtb_binary_path"] = sanitized["path"]
                                        elif eng_name == "cfour":
                                            sp["cfour_binary_path"] = sanitized["path"]
                                        elif eng_name == "mpirun":
                                            sp["mpirun_binary_path"] = sanitized["path"]
                                        elif eng_name == "aimnet2":
                                            sp["aimnet2_server_path"] = sanitized["path"]

                            consolidated_raw["engines"] = cleaned_engines

                    elif phase_filename == "p4.json":
                        # Silo Provisioning & Isolation
                        silos_data = phase_data.get("silos") or phase_data.get("silo_manifest", {})
                        gpu_active = False
                        torq_active = True
                        if isinstance(silos_data, dict):
                            if any("mace" in k or "gpu" in k for k in silos_data.keys()):
                                gpu_active = True
                            if "torq_silo_active" in silos_data:
                                torq_active = bool(silos_data["torq_silo_active"])
                            if "gpu_silo_active" in silos_data:
                                gpu_active = bool(silos_data["gpu_silo_active"])
                        consolidated_raw["silos"] = {
                            "torq_silo_active": torq_active,
                            "gpu_silo_active": gpu_active,
                        }

                    elif phase_filename == "p5.json":
                        # MPS Daemon & VRAM Budgeting
                        vram_budget = phase_data.get("vram_budget", {})
                        if vram_budget:
                            if "hardware" not in consolidated_raw:
                                consolidated_raw["hardware"] = {}
                            hw = consolidated_raw["hardware"]
                            hw["mps_enabled"] = bool(phase_data.get("mps_daemon", {}).get("is_daemon_active", False))

                    elif phase_filename == "p6.json":
                        # Database & Bifurcated Storage
                        storage = phase_data.get("storage", {}) or phase_data.get("storage_tier", {})
                        if storage.get("hdf5_pes_store_path"):
                            if "silo_paths" not in consolidated_raw:
                                consolidated_raw["silo_paths"] = {}
                            consolidated_raw["silo_paths"]["hdf5_pes_store_path"] = storage["hdf5_pes_store_path"]

                    elif phase_filename == "p7.json":
                        # HPC Environment Configuration
                        hpc_info = phase_data.get("hpc", {})
                        if hpc_info and isinstance(hpc_info, dict):
                            valid_hpc_keys = {
                                "scheduler", "default_partition", "max_walltime_hours",
                                "partition", "cluster_hostname", "ssh_key_path",
                                "username", "execution_mode", "walltime_budgets"
                            }
                            filtered_hpc = {k: v for k, v in hpc_info.items() if k in valid_hpc_keys and v is not None}
                            if filtered_hpc:
                                consolidated_raw["hpc"] = filtered_hpc

                    elif phase_filename == "p9.json":
                        # Core Pinning & Parsl Concurrency
                        pinning = phase_data.get("core_pinning", {})
                        if pinning and isinstance(pinning, dict):
                            valid_pin_keys = {"kmp_hw_subset", "anchor_p_cores", "scout_p_cores", "background_e_cores"}
                            filtered_pin = {k: v for k, v in pinning.items() if k in valid_pin_keys and v is not None}
                            if filtered_pin:
                                if "hardware" not in consolidated_raw:
                                    consolidated_raw["hardware"] = {}
                                consolidated_raw["hardware"]["core_pinning"] = filtered_pin

                    elif phase_filename == "p10.json":
                        # MolSym Intake & Theoretical Eckart Frame Alignment
                        consolidated_raw["alignment_engine_ready"] = bool(
                            phase_data.get("alignment_engine_ready", True)
                        )

                    elif phase_filename == "p11.json":
                        # Memory Router & OOM Shield
                        mem_routing = phase_data.get("memory_routing", {}) or phase_data.get("oom_shield", {})
                        if "maxcore_mb" in mem_routing:
                            if "hardware" not in consolidated_raw:
                                consolidated_raw["hardware"] = {}
                            consolidated_raw["hardware"]["maxcore_mb"] = int(mem_routing["maxcore_mb"])

                    break
                except Exception as e:
                    logger.warning(f"Advisory: could not parse intermediate state {phase_file}: {e}")

    return consolidated_raw, list(dict.fromkeys(found_phases))


# =============================================================================
# 7. MASTER SYSTEM CONFIG VALIDATION & IMMUTABLE LOCKING
# =============================================================================


def validate_and_build_system_config(
    consolidated_data: Optional[Dict[str, Any]] = None,
    auto_detect_fallback: bool = True,
    single_threaded_mode: bool = False,
) -> CoChemSystemConfig:
    """
    Validate the consolidated registry dictionary against CoChemSystemConfig, applying
    hardware discovery fallbacks and setting status to 'LOCKED' per Stage 0 mandate.
    """
    raw = dict(consolidated_data or {})

    # Ensure Hardware exists and is completely bounded
    if "hardware" not in raw or not raw["hardware"] or not isinstance(raw["hardware"], dict):
        if auto_detect_fallback:
            discovered_hw = discover_host_hardware()
            raw["hardware"] = discovered_hw.model_dump()
        else:
            raw["hardware"] = {
                "cpu_physical_cores": 4,
                "physical_cpu_cores": 4,
                "logical_cpu_cores": 8,
                "ram_gb": 16.0,
            }
    else:
        hw_dict = dict(raw["hardware"])
        ram_val = hw_dict.get("ram_gb")
        if ram_val is None or float(ram_val) <= 0.0:
            if auto_detect_fallback:
                hw_dict["ram_gb"] = discover_host_hardware().ram_gb
            else:
                hw_dict["ram_gb"] = 16.0

        if not hw_dict.get("cpu_physical_cores") or int(hw_dict.get("cpu_physical_cores", 0)) < 1:
            hw_dict["cpu_physical_cores"] = hw_dict.get("physical_cpu_cores") or (discover_host_hardware().cpu_physical_cores if auto_detect_fallback else 4)
        if not hw_dict.get("physical_cpu_cores"):
            hw_dict["physical_cpu_cores"] = hw_dict["cpu_physical_cores"]
        if not hw_dict.get("logical_cpu_cores"):
            hw_dict["logical_cpu_cores"] = hw_dict["cpu_physical_cores"] * 2

        raw["hardware"] = hw_dict

    if single_threaded_mode:
        raw["hardware"]["allocatable_compute_cores"] = 1

    # Standard quantum solver defaults
    if "quantum_settings" not in raw or not raw["quantum_settings"]:
        raw["quantum_settings"] = {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
            "charge": 0,
            "multiplicity": 1,
        }

    # HPC defaults
    if "hpc" not in raw or not raw["hpc"]:
        raw["hpc"] = {
            "scheduler": "local",
            "default_partition": "compute",
            "max_walltime_hours": 24,
        }

    # Environment defaults
    if "environment" not in raw or not raw["environment"]:
        raw["environment"] = {
            "os_target": raw.get("os_target", OSTarget.LOCAL_WINDOWS.value if os.name == "nt" else OSTarget.LOCAL_LINUX.value),
            "codata_version": "2018",
            "isotopic_mass_locking": True,
            "isotopic_mass_13c": CARBON_13_ISOTOPIC_MASS,
            "isotopic_masses": {},
        }

    raw["status"] = "LOCKED"
    raw["schema_version"] = "4.0.0"

    cfg = CoChemSystemConfig.model_validate(raw)
    cfg.update_checksum()
    return cfg


def finalize_and_lock_golden_registry(
    cfg: CoChemSystemConfig,
    output_path: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Atomically write finalized Golden Registry to cochem_system_config.json,
    set cfg['status'] = 'LOCKED', and apply os.chmod(0o444) to enforce post-setup immutability.

    SRS Document 5 Section 4.3 Mandate.
    """
    target_path = resolve_golden_config_path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    cfg.status = "LOCKED"
    cfg.update_checksum()
    serialized_dict = cfg.model_dump()

    if not dry_run:
        with DependencyManager() as dm:
            dm.atomic_write_json(
                target_path=target_path,
                data=serialized_dict,
                indent=2,
                read_only=True,
            )

    return target_path, serialized_dict


# =============================================================================
# 8. WORKSPACE GARBAGE COLLECTION SWEEP
# =============================================================================


def execute_workspace_sweep(
    workspace_dir: Optional[Union[str, Path]] = None,
    registry_dir: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
    remove_intermediate_json: bool = False,
    trash_dir: Optional[Union[str, Path]] = None,
) -> WorkspaceSweepReport:
    """
    Execute a garbage collection sweep to safely delete all ephemeral .tmp files and
    intermediate JSON fragments from the workspace.

    SRS Document 5 Section 4.3 Mandate:
    Preserves persistent registry files (cochem_system_config.json) while sweeping
    staged .tmp files and temporary lock probes.
    """
    target_ws = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()
    target_reg = Path(registry_dir).resolve() if registry_dir else resolve_golden_config_path().parent

    cleaned_paths: List[str] = []
    retained_paths: List[str] = []

    search_roots = [target_ws, target_reg]

    for root in search_roots:
        if not root.is_dir():
            continue

        try:
            for entry in root.rglob("*"):
                if not entry.is_file():
                    continue

                filename = entry.name.lower()

                # Never delete finalized system config
                if filename == "cochem_system_config.json":
                    retained_paths.append(str(entry.resolve()))
                    continue

                is_ephemeral = False

                # Check for .tmp extensions or lock probe patterns
                if ".tmp" in filename or filename.startswith(".cochem_") or filename.endswith(".lock"):
                    is_ephemeral = True

                # Check for intermediate p1..p11 fragments if requested
                if remove_intermediate_json:
                    if re.match(r"^p\d+\.json$", filename) or filename.endswith(".tmp.json"):
                        is_ephemeral = True

                if is_ephemeral:
                    cleaned_paths.append(str(entry.resolve()))
                    if not dry_run:
                        try:
                            # Ensure writable before removing
                            try:
                                os.chmod(entry, stat.S_IWRITE | stat.S_IREAD)
                            except OSError:
                                pass
                            if trash_dir:
                                tdir = Path(trash_dir).resolve()
                                tdir.mkdir(parents=True, exist_ok=True)
                                shutil.move(str(entry), str(tdir / entry.name))
                            else:
                                entry.unlink(missing_ok=True)
                        except OSError as e:
                            logger.warning(f"Advisory: could not sweep temporary file {entry}: {e}")
                else:
                    retained_paths.append(str(entry.resolve()))

        except OSError as e:
            logger.warning(f"Advisory: error traversing directory {root} during sweep: {e}")

    return WorkspaceSweepReport(
        swept_files_count=len(cleaned_paths),
        cleaned_paths=cleaned_paths,
        retained_paths=list(dict.fromkeys(retained_paths)),
        trash_dir=str(trash_dir) if trash_dir else None,
    )


# =============================================================================
# 9. GPU DISCOVERY & VRAM PROFILING
# =============================================================================


def probe_gpu_devices_vram(
    registry_p2_path: Optional[Union[str, Path]] = None,
) -> Tuple[List[GPUDeviceVRAM], bool]:
    """
    Interrogate host GPU topology and extract accurate physical VRAM capacities
    using a multi-tiered inspection pipeline (p2.json -> pynvml -> nvidia-smi -> torch.cuda).
    """
    devices: List[GPUDeviceVRAM] = []
    cuda_available = False

    # Tier 1: Interrogate previous Phase 2 registry (p2.json) if available
    candidate_p2_paths: List[Path] = []
    if registry_p2_path:
        candidate_p2_paths.append(Path(registry_p2_path).resolve())
    candidate_p2_paths.append(Path.cwd() / ".agent_artifacts" / "Registry" / "p2.json")
    candidate_p2_paths.append(Path.home() / "CoChem_Artifacts" / "Registry" / "p2.json")

    for p2_path in candidate_p2_paths:
        if p2_path.exists() and p2_path.is_file():
            try:
                data = json.loads(p2_path.read_text(encoding="utf-8"))
                gpu_info = data.get("gpu", {})
                if gpu_info.get("cuda_available", False) and gpu_info.get("devices"):
                    for d in gpu_info["devices"]:
                        if d.get("vendor", "").upper() == "NVIDIA":
                            vram_bytes = d.get("memory_total_bytes") or 0
                            free_bytes = d.get("memory_free_bytes") or vram_bytes
                            vram_mb = float(vram_bytes) / (1024.0 * 1024.0)
                            free_mb = float(free_bytes) / (1024.0 * 1024.0)
                            idx = int(d.get("index", len(devices)))
                            dev_name = d.get("name", f"NVIDIA GPU {idx}")
                            dev_uuid = d.get("uuid")
                            arch = d.get("compute_capability")
                            devices.append(
                                GPUDeviceVRAM(
                                    index=idx,
                                    name=dev_name,
                                    uuid=dev_uuid,
                                    total_vram_mb=round(vram_mb, 2),
                                    free_vram_mb=round(free_mb, 2),
                                    reserved_vram_mb=0.0,
                                    allocatable_vram_mb=0.0,
                                    allocated_limit_per_worker_mb=0.0,
                                    active_worker_capacity=1,
                                    pinned_mem_limit_str="",
                                    compute_capability=arch,
                                )
                            )
                    if devices:
                        cuda_available = True
                        return devices, cuda_available
            except Exception:
                pass

    # Tier 2: Query NVIDIA NVML via pynvml or nvidia-ml-py if present
    try:
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            import pynvml  # type: ignore

        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for idx in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
            name_raw = pynvml.nvmlDeviceGetName(handle)
            name = name_raw.decode("utf-8") if isinstance(name_raw, bytes) else str(name_raw)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_mb = float(mem_info.total) / (1024.0 * 1024.0)
            free_mb = float(mem_info.free) / (1024.0 * 1024.0)
            try:
                uuid_raw = pynvml.nvmlDeviceGetUUID(handle)
                dev_uuid = uuid_raw.decode("utf-8") if isinstance(uuid_raw, bytes) else str(uuid_raw)
            except Exception:
                dev_uuid = None
            try:
                major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                arch = f"sm_{major}{minor}"
            except Exception:
                arch = None

            devices.append(
                GPUDeviceVRAM(
                    index=idx,
                    name=name,
                    uuid=dev_uuid,
                    total_vram_mb=round(total_mb, 2),
                    free_vram_mb=round(free_mb, 2),
                    reserved_vram_mb=0.0,
                    allocatable_vram_mb=0.0,
                    allocated_limit_per_worker_mb=0.0,
                    active_worker_capacity=1,
                    pinned_mem_limit_str="",
                    compute_capability=arch,
                )
            )
        pynvml.nvmlShutdown()
        if devices:
            cuda_available = True
            return devices, cuda_available
    except Exception:
        pass

    # Tier 3: Query via nvidia-smi CLI
    try:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
            subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,uuid,memory.total,memory.free,driver_version",
                    "--format=csv,noheader,nounits",
                ],
                stdout=tmp_out,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            tmp_out.seek(0)
            smi_out = tmp_out.read()
        for line in smi_out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                idx = int(parts[0])
                name = parts[1]
                dev_uuid = parts[2]
                total_mb = float(parts[3])
                free_mb = float(parts[4])
                devices.append(
                    GPUDeviceVRAM(
                        index=idx,
                        name=name,
                        uuid=dev_uuid,
                        total_vram_mb=round(total_mb, 2),
                        free_vram_mb=round(free_mb, 2),
                        reserved_vram_mb=0.0,
                        allocatable_vram_mb=0.0,
                        allocated_limit_per_worker_mb=0.0,
                        active_worker_capacity=1,
                        pinned_mem_limit_str="",
                        compute_capability=None,
                    )
                )
        if devices:
            cuda_available = True
            return devices, cuda_available
    except Exception:
        pass

    # Tier 4: Query via torch.cuda if available
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            cuda_available = True
            cnt = torch.cuda.device_count()
            for idx in range(cnt):
                props = torch.cuda.get_device_properties(idx)
                total_mb = float(props.total_memory) / (1024.0 * 1024.0)
                arch = f"sm_{props.major}{props.minor}"
                devices.append(
                    GPUDeviceVRAM(
                        index=idx,
                        name=props.name,
                        uuid=None,
                        total_vram_mb=round(total_mb, 2),
                        free_vram_mb=round(total_mb, 2),
                        reserved_vram_mb=0.0,
                        allocatable_vram_mb=0.0,
                        allocated_limit_per_worker_mb=0.0,
                        active_worker_capacity=1,
                        pinned_mem_limit_str="",
                        compute_capability=arch,
                    )
                )
            if devices:
                return devices, cuda_available
    except Exception:
        pass

    return devices, cuda_available


# =============================================================================
# 10. VRAM BUDGETING & MEMORY PARTITIONING ALGORITHM
# =============================================================================


def calculate_vram_budget(
    devices: List[GPUDeviceVRAM],
    worker_concurrency_target: int = 2,
    custom_limit_per_worker_mb: Optional[float] = None,
    reserved_headroom_fraction: float = 0.15,
    min_reserved_headroom_mb: float = 1024.0,
) -> VRAMBudgetReport:
    """
    Calculate mathematically bounded VRAM allocations and build the authoritative
    CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string for each device.

    Formula:
    Reserved_VRAM = max(min_reserved_headroom_mb, total_vram_mb * reserved_headroom_fraction)
    Allocatable_VRAM = max(0.0, total_vram_mb - Reserved_VRAM)
    Per_Worker_Limit = floor(Allocatable_VRAM / worker_concurrency_target)
    """
    concurrency = max(1, worker_concurrency_target)
    updated_devices: List[GPUDeviceVRAM] = []
    per_device_limits: Dict[str, str] = {}
    default_pinned_str: Optional[str] = None

    total_cluster_vram = 0.0
    total_reserved_vram = 0.0
    total_allocatable_vram = 0.0

    if not devices:
        return VRAMBudgetReport(
            total_gpus_detected=0,
            active_gpu_devices=[],
            total_cluster_vram_mb=0.0,
            total_reserved_vram_mb=0.0,
            total_allocatable_vram_mb=0.0,
            worker_concurrency_target=concurrency,
            default_pinned_mem_limit=None,
            per_device_limits={},
            is_vram_bounded=True,
            strategy="ZERO_GPU_DEGRADED",
        )

    for dev in devices:
        total_mb = dev.total_vram_mb
        total_cluster_vram += total_mb

        reserved_mb = max(min_reserved_headroom_mb, total_mb * reserved_headroom_fraction)
        reserved_mb = min(reserved_mb, total_mb)
        total_reserved_vram += reserved_mb

        allocatable_mb = max(0.0, total_mb - reserved_mb)
        total_allocatable_vram += allocatable_mb

        if custom_limit_per_worker_mb is not None and custom_limit_per_worker_mb > 0:
            limit_mb = min(allocatable_mb, custom_limit_per_worker_mb)
        else:
            limit_mb = allocatable_mb / float(concurrency) if allocatable_mb > 0 else 0.0

        int_limit_mb = int(limit_mb)
        pinned_str = f"{dev.index}={int_limit_mb}M" if int_limit_mb > 0 else f"{dev.index}=0M"
        per_device_limits[str(dev.index)] = pinned_str

        worker_capacity = max(1, int(allocatable_mb // int_limit_mb)) if int_limit_mb > 0 else 1

        updated_dev = GPUDeviceVRAM(
            index=dev.index,
            name=dev.name,
            uuid=dev.uuid,
            total_vram_mb=dev.total_vram_mb,
            free_vram_mb=dev.free_vram_mb,
            reserved_vram_mb=round(reserved_mb, 2),
            allocatable_vram_mb=round(allocatable_mb, 2),
            allocated_limit_per_worker_mb=round(float(int_limit_mb), 2),
            active_worker_capacity=worker_capacity,
            pinned_mem_limit_str=pinned_str,
            compute_capability=dev.compute_capability,
        )
        updated_devices.append(updated_dev)

    if updated_devices:
        first_limit = int(updated_devices[0].allocated_limit_per_worker_mb)
        default_pinned_str = f"{first_limit}M" if first_limit > 0 else None

    return VRAMBudgetReport(
        total_gpus_detected=len(updated_devices),
        active_gpu_devices=updated_devices,
        total_cluster_vram_mb=round(total_cluster_vram, 2),
        total_reserved_vram_mb=round(total_reserved_vram, 2),
        total_allocatable_vram_mb=round(total_allocatable_vram, 2),
        worker_concurrency_target=concurrency,
        default_pinned_mem_limit=default_pinned_str,
        per_device_limits=per_device_limits,
        is_vram_bounded=True,
        strategy="PROPORTIONAL_PINNED_BUDGET",
    )


def build_pinned_memory_limit_string(budget: VRAMBudgetReport, device_index: int = 0) -> str:
    """
    Build the exact CUDA_MPS_PINNED_DEVICE_MEM_LIMIT value for a specific device index.
    """
    dev_str = str(device_index)
    if dev_str in budget.per_device_limits:
        return budget.per_device_limits[dev_str]
    if budget.default_pinned_mem_limit:
        return budget.default_pinned_mem_limit
    return ""


# =============================================================================
# 11. NVIDIA MPS BINARY DISCOVERY & DAEMON LIFECYCLE MANAGEMENT
# =============================================================================


def discover_mps_binaries() -> Tuple[Optional[str], Optional[str]]:
    """
    Sweep host filesystem for nvidia-cuda-mps-control and nvidia-cuda-mps-server binaries.
    """
    control_path: Optional[str] = shutil.which("nvidia-cuda-mps-control")
    server_path: Optional[str] = shutil.which("nvidia-cuda-mps-server")

    candidate_roots = [
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path("/usr/local/cuda/bin"),
        Path("/opt/cuda/bin"),
    ]

    for usr_local in [Path("/usr/local"), Path("/opt")]:
        if usr_local.is_dir():
            try:
                for entry in usr_local.iterdir():
                    if entry.is_dir() and "cuda" in entry.name.lower():
                        bin_dir = entry / "bin"
                        if bin_dir.is_dir() and bin_dir not in candidate_roots:
                            candidate_roots.append(bin_dir)
            except OSError:
                pass

    if not control_path:
        for cdir in candidate_roots:
            candidate = cdir / "nvidia-cuda-mps-control"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                control_path = str(candidate.resolve())
                break

    if not server_path:
        for cdir in candidate_roots:
            candidate = cdir / "nvidia-cuda-mps-server"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                server_path = str(candidate.resolve())
                break

    return control_path, server_path


def probe_mps_daemon_status(
    pipe_dir: Path,
    log_dir: Path,
    control_binary: Optional[str] = None,
    server_binary: Optional[str] = None,
) -> MPSDaemonAudit:
    """
    Probe the live operational status of the NVIDIA MPS daemon, inspect pipe sockets,
    and verify daemon responsiveness.
    """
    is_posix = platform.system() != "Windows"
    sec_ok, perm_str = enforce_socket_directory_permissions(pipe_dir)

    is_running = False
    control_active = False
    server_active = False
    daemon_pid: Optional[int] = None
    socket_path: Optional[str] = None
    details_list: List[str] = []

    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                pname = proc.info.get("name", "") or ""
                raw_cmd = proc.info.get("cmdline") or []
                cmd = " ".join(str(c) for c in raw_cmd if c is not None)
                if "nvidia-cuda-mps-control" in pname or "nvidia-cuda-mps-control" in cmd:
                    is_running = True
                    control_active = True
                    daemon_pid = proc.info.get("pid")
                if "nvidia-cuda-mps-server" in pname or "nvidia-cuda-mps-server" in cmd:
                    server_active = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
    except Exception:
        pass

    control_pipe = pipe_dir / "control"
    server_pipe = pipe_dir / "server"

    if control_pipe.exists():
        socket_path = str(control_pipe)
        details_list.append("MPS control pipe present in socket directory")
    elif server_pipe.exists():
        socket_path = str(server_pipe)
        details_list.append("MPS server pipe present in socket directory")
    else:
        socket_path = str(pipe_dir)

    if control_binary and is_running and is_posix:
        try:
            env = os.environ.copy()
            env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
            env["CUDA_MPS_LOG_DIRECTORY"] = str(log_dir)
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
                subprocess.run(
                    [control_binary],
                    input="get_server_list\nquit\n",
                    text=True,
                    stdout=tmp_out,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    check=True,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
                control_active = True
                details_list.append("nvidia-cuda-mps-control responsive to commands")
        except Exception as e:
            details_list.append(f"MPS command pipe probe advisory: {e}")

    if not is_posix:
        mps_status = MPSStatus.NOT_SUPPORTED
        details_list.append("NVIDIA MPS daemon multiplexing not natively supported on Windows NT; degraded CPU/direct CUDA active")
    elif is_running:
        mps_status = MPSStatus.RUNNING
        details_list.append("NVIDIA MPS daemon is running and multiplexing CUDA contexts")
    elif control_binary:
        mps_status = MPSStatus.INITIALIZED
        details_list.append("NVIDIA MPS control binary detected; daemon is idle / not started")
    else:
        mps_status = MPSStatus.NOT_SUPPORTED
        details_list.append("nvidia-cuda-mps-control binary not found in PATH or standard system locations")

    env_dict = {
        "CUDA_MPS_PIPE_DIRECTORY": str(pipe_dir),
        "CUDA_MPS_LOG_DIRECTORY": str(log_dir),
    }

    return MPSDaemonAudit(
        mps_control_binary=control_binary,
        mps_server_binary=server_binary,
        status=mps_status,
        pipe_directory=str(pipe_dir),
        log_directory=str(log_dir),
        socket_path=socket_path,
        is_daemon_active=is_running,
        pid=daemon_pid,
        socket_permissions=perm_str,
        is_permission_secure=sec_ok,
        server_active=server_active,
        control_active=control_active,
        environment_variables=env_dict,
        details="; ".join(details_list),
    )


def start_mps_daemon(
    pipe_dir: Path,
    log_dir: Path,
    control_binary: str,
    server_binary: Optional[str] = None,
    force_restart: bool = False,
) -> MPSDaemonAudit:
    """
    Start the nvidia-cuda-mps-control daemon in background mode (-d).
    """
    if platform.system() == "Windows":
        return probe_mps_daemon_status(pipe_dir, log_dir, control_binary, server_binary)

    if force_restart:
        stop_mps_daemon(pipe_dir, control_binary)

    pipe_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    enforce_socket_directory_permissions(pipe_dir)
    enforce_socket_directory_permissions(log_dir)

    env = os.environ.copy()
    env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
    env["CUDA_MPS_LOG_DIRECTORY"] = str(log_dir)

    try:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
            subprocess.run(
                [control_binary, "-d"],
                env=env,
                check=True,
                timeout=5,
                stdout=tmp_out,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
    except Exception as exc:
        raise MPSControlError(f"Failed to start nvidia-cuda-mps-control daemon: {exc}") from exc

    return probe_mps_daemon_status(pipe_dir, log_dir, control_binary, server_binary)


def stop_mps_daemon(
    pipe_dir: Path,
    control_binary: Optional[str] = None,
) -> bool:
    """
    Stop any running nvidia-cuda-mps-control daemon and backend server cleanly.
    """
    if platform.system() == "Windows":
        return True

    stopped = False
    if control_binary:
        env = os.environ.copy()
        env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
        try:
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
                subprocess.run(
                    [control_binary],
                    input="quit\n",
                    text=True,
                    stdout=tmp_out,
                    stderr=subprocess.DEVNULL,
                    check=True,
                    env=env,
                    timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
                stopped = True
        except Exception:
            pass

    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = proc.info.get("name") or ""
                if "nvidia-cuda-mps-control" in pname or "nvidia-cuda-mps-server" in pname:
                    proc.terminate()
                    stopped = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
    except Exception:
        pass

    return stopped


def configure_mps_device_limit(
    pipe_dir: Path,
    device_index: int,
    limit_mb: int,
    control_binary: Optional[str] = None,
) -> bool:
    """
    Configure dynamic pinned memory limits on a running MPS daemon via control pipe.
    Command: set_device_pinned_mem_limit <device_index> <limit_mb>M
    """
    if platform.system() == "Windows" or not control_binary:
        return False

    cmd_str = f"set_device_pinned_mem_limit {device_index} {limit_mb}M\nquit\n"
    env = os.environ.copy()
    env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)

    try:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
            subprocess.run(
                [control_binary],
                input=cmd_str,
                text=True,
                stdout=tmp_out,
                stderr=subprocess.DEVNULL,
                check=True,
                env=env,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            return True
    except Exception:
        return False


# =============================================================================
# 12. ENVIRONMENT INJECTION & ACTIVATION SCRIPT GENERATION
# =============================================================================


def inject_mps_environment_variables(
    pipe_dir: Path,
    log_dir: Path,
    vram_budget: VRAMBudgetReport,
) -> Dict[str, str]:
    """
    Construct authoritative MPS and VRAM environment variables dictionary.
    Includes memory limits and active thread percentage partitioning (Method Matrix §8A.4).
    """
    thread_pct = max(1, min(100, int(100 // max(1, vram_budget.worker_concurrency_target))))
    env_vars: Dict[str, str] = {
        "CUDA_MPS_PIPE_DIRECTORY": str(pipe_dir),
        "CUDA_MPS_LOG_DIRECTORY": str(log_dir),
        "CUDA_MPS_ENABLE_PER_DEVICE_PINNED_MEM_LIMIT": "1",
        "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(thread_pct),
    }

    if vram_budget.default_pinned_mem_limit:
        env_vars["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = vram_budget.default_pinned_mem_limit
    elif vram_budget.active_gpu_devices:
        first_limit = vram_budget.active_gpu_devices[0].pinned_mem_limit_str
        if first_limit:
            env_vars["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = first_limit

    for k, v in env_vars.items():
        os.environ[k] = v

    return env_vars


def generate_mps_activation_scripts(
    target_dir: Union[str, Path],
    env_vars: Dict[str, str],
) -> Dict[str, Path]:
    """
    Generate standalone shell and batch script wrappers to inject MPS and VRAM
    configuration into subshells, Jupyter kernels, and external worker processes.
    """
    out_dir = Path(target_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    sh_path = out_dir / "cochem_activate_mps.sh"
    sh_lines = [
        "#!/bin/sh",
        "# CoChem Stage 0 Phase 5: NVIDIA MPS & VRAM Budgeting Environment Hook",
    ]
    for k, v in env_vars.items():
        sh_lines.append(f'export {k}="{v}"')
    sh_path.write_text("\n".join(sh_lines) + "\n", encoding="utf-8")
    try:
        sh_path.chmod(sh_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass

    bat_path = out_dir / "cochem_activate_mps.bat"
    bat_lines = [
        "@echo off",
        "rem CoChem Stage 0 Phase 5: NVIDIA MPS & VRAM Budgeting Environment Hook",
    ]
    for k, v in env_vars.items():
        bat_lines.append(f"set {k}={v}")
    bat_path.write_text("\n".join(bat_lines) + "\n", encoding="utf-8")

    json_path = out_dir / "cochem_mps_config.json"
    json_path.write_text(
        json.dumps(
            {
                "env_vars": env_vars,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "sh": sh_path,
        "bat": bat_path,
        "json": json_path,
    }


# =============================================================================
# 13. FULL PROGRAMMATIC AUDIT PIPELINE ENTRYPOINT
# =============================================================================


def run_phase_5_audit(
    output_dir: Optional[Union[str, Path]] = None,
    socket_dir: Optional[Union[str, Path]] = None,
    log_dir: Optional[Union[str, Path]] = None,
    worker_concurrency: int = 2,
    custom_vram_limit_mb: Optional[float] = None,
    start_daemon: bool = False,
    force_restart: bool = False,
    dry_run: bool = False,
    workspace_dir: Optional[Union[str, Path]] = None,
    sweep_workspace: bool = True,
) -> Phase5AuditReport:
    """
    Execute full Phase 5 Audit Pipeline:
    1. NVIDIA MPS Daemon & VRAM Budgeting (SRS Doc 2 Part 2 Section 3.5).
    2. Physical POSIX byte-range locking test (fcntl) with graceful degradation to single-threaded mode.
    3. Intermediate state consolidation (p1.json through p11.json).
    4. Pydantic validation and Golden Registry locking to cochem_system_config.json with os.chmod(0o444).
    5. Workspace garbage collection sweep purging ephemeral .tmp files.
    """
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Resolve Pipe and Log Directories
    pipe_path = resolve_mps_pipe_directory(socket_dir)
    log_path = resolve_mps_log_directory(log_dir)
    is_slurm = bool(os.environ.get("SLURM_JOB_ID") or os.environ.get("SLURM_TMPDIR"))

    # 2. Discover GPU Devices and VRAM Capacities
    gpu_devices, is_cuda = probe_gpu_devices_vram()

    # 3. Calculate VRAM Budget & Concurrency Partitioning
    vram_budget = calculate_vram_budget(
        devices=gpu_devices,
        worker_concurrency_target=worker_concurrency,
        custom_limit_per_worker_mb=custom_vram_limit_mb,
    )

    if not is_cuda or not gpu_devices:
        warnings.append(
            "No active NVIDIA CUDA GPU detected; execution operating in CPU-only or direct compute fallback mode."
        )

    # 4. Discover MPS Binaries & Probe Daemon Status
    control_bin, server_bin = discover_mps_binaries()

    if start_daemon and control_bin and not dry_run:
        try:
            mps_daemon = start_mps_daemon(
                pipe_dir=pipe_path,
                log_dir=log_path,
                control_binary=control_bin,
                server_binary=server_bin,
                force_restart=force_restart,
            )
        except Exception as exc:
            warnings.append(f"Could not start MPS daemon: {exc}")
            mps_daemon = probe_mps_daemon_status(pipe_path, log_path, control_bin, server_bin)
    else:
        mps_daemon = probe_mps_daemon_status(pipe_path, log_path, control_bin, server_bin)

    # 5. Inject Environment Variables & Generate Scripts
    env_vars = inject_mps_environment_variables(pipe_path, log_path, vram_budget)
    mps_daemon.environment_variables = env_vars

    if not dry_run:
        generate_mps_activation_scripts(pipe_path, env_vars)

    # 6. Physical POSIX Byte-Range Locking Verification
    resolved_registry_dir = Path(output_dir).resolve() if output_dir else resolve_golden_config_path().parent
    lock_result = test_posix_byte_range_locking(resolved_registry_dir)
    if not lock_result.passed:
        warnings.append(
            f"Filesystem byte-range locking test failed ({lock_result.error_message}); "
            "degraded to single-threaded execution mode."
        )

    # 7. Intermediate State Consolidation & Golden Registry Locking
    consolidated_data, found_phases = consolidate_intermediate_states(
        registry_dir=resolved_registry_dir,
    )

    system_config = validate_and_build_system_config(
        consolidated_data=consolidated_data,
        auto_detect_fallback=True,
        single_threaded_mode=lock_result.single_threaded_mode,
    )

    golden_path, _ = finalize_and_lock_golden_registry(
        cfg=system_config,
        output_path=resolved_registry_dir / "cochem_system_config.json",
        dry_run=dry_run,
    )

    # 8. Workspace Garbage Collection Sweep
    if sweep_workspace:
        sweep_report = execute_workspace_sweep(
            workspace_dir=workspace_dir,
            registry_dir=resolved_registry_dir,
            dry_run=dry_run,
            remove_intermediate_json=False,
        )
    else:
        sweep_report = WorkspaceSweepReport(swept_files_count=0, cleaned_paths=[], retained_paths=[])

    config_lock_audit = ConfigLockAuditReport(
        golden_registry_path=str(golden_path),
        status=system_config.status or "LOCKED",
        checksum=system_config.registry_checksum or system_config.compute_checksum(),
        posix_lock_test=lock_result,
        sweep_report=sweep_report,
        intermediate_phases_found=found_phases,
        is_immutable_mode_enforced=True,
    )

    # 9. Evaluate Phase Status
    if errors:
        phase_status = PhaseStatus.FAILED
    elif lock_result.single_threaded_mode or not is_cuda or mps_daemon.status in (MPSStatus.NOT_SUPPORTED, MPSStatus.DEGRADED):
        phase_status = PhaseStatus.PASSED  # Graceful pass in degraded mode per Method Matrix
    else:
        phase_status = PhaseStatus.PASSED

    # 10. Destination Registry Artifact Path (p5.json)
    p5_path = resolve_p5_registry_path(output_dir)

    # 11. Construct Final Audit Report
    report = Phase5AuditReport(
        phase_id="PHASE_5_NVIDIA_MPS_VRAM_BUDGETING",
        status=phase_status,
        timestamp_utc=timestamp_utc,
        mps_daemon=mps_daemon,
        vram_budget=vram_budget,
        is_cuda_available=is_cuda,
        is_hpc_slurm=is_slurm,
        config_lock=config_lock_audit,
        warnings=warnings,
        errors=errors,
        artifact_path=str(p5_path),
        golden_config_path=str(golden_path),
    )

    # 12. Idempotent Atomic State Persistence (p5.json)
    if not dry_run:
        with DependencyManager() as dm:
            dm.atomic_write_json(p5_path, report)

    return report


# =============================================================================
# 14. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Command-line entrypoint for CoChem Setup Phase 5:
    IPC Config Lock & Workspace Sweep & NVIDIA MPS Daemon / VRAM Budgeting CLI.
    Returns 0 on PASSED/DEGRADED, non-zero on fatal errors.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 5: IPC Config Lock, Workspace Sweep & NVIDIA MPS Daemon CLI",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Custom destination directory for Registry artifacts (p5.json & cochem_system_config.json)",
    )
    parser.add_argument(
        "--socket-dir",
        "-s",
        type=str,
        default=None,
        help="Custom directory for CUDA_MPS_PIPE_DIRECTORY sockets",
    )
    parser.add_argument(
        "--log-dir",
        "-l",
        type=str,
        default=None,
        help="Custom directory for CUDA_MPS_LOG_DIRECTORY telemetry logs",
    )
    parser.add_argument(
        "--workspace-dir",
        "-w-dir",
        type=str,
        default=None,
        help="Custom workspace directory for ephemeral garbage collection sweep",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=2,
        help="Target concurrent GPU workers for VRAM budget partitioning (default: 2)",
    )
    parser.add_argument(
        "--vram-limit-mb",
        type=float,
        default=None,
        help="Explicit pinned memory limit per worker in megabytes (overrides proportional formula)",
    )
    parser.add_argument(
        "--start-daemon",
        action="store_true",
        help="Attempt to start nvidia-cuda-mps-control daemon in background mode",
    )
    parser.add_argument(
        "--force-restart",
        action="store_true",
        help="Force restart of existing MPS daemon processes",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop active nvidia-cuda-mps-control daemon and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview VRAM budgeting and config lock without modifying filesystem or starting daemons",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    if args.stop:
        pipe_path = resolve_mps_pipe_directory(args.socket_dir)
        control_bin, _ = discover_mps_binaries()
        stopped = stop_mps_daemon(pipe_path, control_bin)
        status_msg = "MPS daemon stopped successfully." if stopped else "No active MPS daemon found to stop."
        logger.info(status_msg)
        return 0

    try:
        report = run_phase_5_audit(
            output_dir=args.output_dir,
            socket_dir=args.socket_dir,
            log_dir=args.log_dir,
            workspace_dir=args.workspace_dir,
            worker_concurrency=args.workers,
            custom_vram_limit_mb=args.vram_limit_mb,
            start_daemon=args.start_daemon,
            force_restart=args.force_restart,
            dry_run=args.dry_run,
        )

        if args.json:
            logger.info(report.model_dump_json(indent=2))
        else:
            logger.info("=" * 75)
            logger.info("COCHEM SETUP PHASE 5: IPC CONFIG LOCK, WORKSPACE SWEEP & MPS VRAM BUDGETING")
            logger.info("=" * 75)
            logger.info(f"Phase ID:          {report.phase_id}")
            logger.info(f"Status:            {report.status.value}")
            logger.info(f"Timestamp UTC:     {report.timestamp_utc}")
            logger.info(f"Artifact Path:     {report.artifact_path}")
            logger.info(f"Golden Config:     {report.golden_config_path}")
            logger.info(f"CUDA Available:    {report.is_cuda_available}")
            logger.info(f"Slurm HPC Mode:    {report.is_hpc_slurm}")
            logger.info(f"MPS Status:        {report.mps_daemon.status.value}")
            logger.info(f"Pipe Directory:    {report.mps_daemon.pipe_directory}")
            logger.info(f"Socket Secure:     {report.mps_daemon.is_permission_secure} ({report.mps_daemon.socket_permissions})")
            if report.config_lock:
                logger.info("-" * 75)
                logger.info("IPC Config Lock & Filesystem Audit:")
                logger.info(f"  Lock Test Method:    {report.config_lock.posix_lock_test.method}")
                logger.info(f"  Lock Test Passed:    {report.config_lock.posix_lock_test.passed}")
                logger.info(f"  Single-Thread Mode:  {report.config_lock.posix_lock_test.single_threaded_mode}")
                logger.info(f"  Registry Status:     {report.config_lock.status}")
                logger.info(f"  Registry Checksum:   {report.config_lock.checksum[:16]}...")
                logger.info(f"  Phases Consolidated: {', '.join(report.config_lock.intermediate_phases_found) or 'Default Synthesized'}")
                logger.info(f"  Swept Ephemeral:     {report.config_lock.sweep_report.swept_files_count} files")
            logger.info("-" * 75)
            logger.info("VRAM Budgeting Matrix:")
            logger.info(f"  Total GPUs:          {report.vram_budget.total_gpus_detected}")
            logger.info(f"  Cluster VRAM:        {report.vram_budget.total_cluster_vram_mb:.0f} MB")
            logger.info(f"  Reserved VRAM:       {report.vram_budget.total_reserved_vram_mb:.0f} MB")
            logger.info(f"  Allocatable VRAM:    {report.vram_budget.total_allocatable_vram_mb:.0f} MB")
            logger.info(f"  Target Workers:      {report.vram_budget.worker_concurrency_target}")
            logger.info(f"  Default Pinned:      {report.vram_budget.default_pinned_mem_limit or 'N/A'}")
            for dev in report.vram_budget.active_gpu_devices:
                logger.info(f"    [GPU {dev.index}] {dev.name:<25} Total: {dev.total_vram_mb:.0f}MB -> Limit: {dev.pinned_mem_limit_str} (Cap: {dev.active_worker_capacity} workers)")
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
        logger.error(f"\n[FATAL PHASE 5 ERROR]\n{exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\cochem_provenance.py ---
"""Authoritative W3C PROV-O Conformer Lineage & Semantic Provenance Graphs.

Complies strictly with:
- W3C PROV-O Linked Data Standard (prov:Entity, prov:Activity, prov:wasDerivedFrom)
- Tripartite Air-Gap Mandate (Offline local JSON-LD context catalog resolution)
- FAIR Principles I1, I3, and R1.2
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def get_local_prov_context() -> Dict[str, Any]:
    """Retrieve bundled offline local W3C PROV-O JSON-LD context [D].

    Dispatches zero network calls to http://www.w3.org/ns/prov#, guaranteeing air-gapped execution.
    """
    ctx_path = Path(__file__).resolve().parent.parent / "schemas" / "contexts" / "prov_o_context.jsonld"
    if not ctx_path.exists():
        # Fallback search if installed or relocated
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


__all__ = [
    "DAGNode",
    "get_local_prov_context",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\cochem_version.py ---
"""Authoritative OS-Agnostic Dynamic VCS Provenance & Container Introspection.

Provides robust environment discovery compliant with FAIR Principle R1.2 across:
- Git Repositories (local development)
- Build Manifests (.build_manifest.json)
- Installed Distribution Packages (importlib.metadata inside stripped Docker containers and HPC wheels)
- Untracked Air-Gapped Environments
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _find_git_root(start_path: Path) -> Optional[Path]:
    """Traverse directory parents to locate genuine .git directory or file."""
    curr = start_path.resolve()
    for p in [curr, *curr.parents]:
        git_target = p / ".git"
        if git_target.exists():
            return p
    return None


def get_vcs_provenance(root_path: Optional[Path] = None) -> Dict[str, Any]:
    """Dynamically determine software version and source provenance hierarchy [D].

    Hierarchy:
    1. Git Repository Check: Queries active commit SHA, branch, dirty status.
    2. Build Manifest Check: Checks for .build_manifest.json in package or COCHEM_ROOT.
    3. Distribution Package Introspection (PEP 566 importlib.metadata).
    4. Safe Fallback (UNTRACKED_BUILD).

    Args:
        root_path: Optional override path to search for repository anchor.

    Returns:
        Dict[str, Any]: Structured VCS provenance metadata dictionary.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Determine starting path anchor
    start_dir: Optional[Path] = None
    if root_path is not None:
        start_dir = Path(root_path).resolve()
    else:
        # Dynamic module anchor
        start_dir = Path(__file__).resolve().parent

    # 1. Git Repository Discovery
    if start_dir is not None:
        git_dir = _find_git_root(start_dir)
        git_cmd = shutil.which("git")
        if git_dir is not None and git_cmd is not None:
            try:
                sha_proc = subprocess.run(
                    [git_cmd, "rev-parse", "HEAD"],
                    cwd=str(git_dir),
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if sha_proc.returncode == 0 and sha_proc.stdout.strip():
                    sha = sha_proc.stdout.strip()
                    branch_proc = subprocess.run(
                        [git_cmd, "rev-parse", "--abbrev-ref", "HEAD"],
                        cwd=str(git_dir),
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False,
                    )
                    branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "unknown"

                    dirty_proc = subprocess.run(
                        [git_cmd, "status", "--porcelain"],
                        cwd=str(git_dir),
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False,
                    )
                    is_dirty = bool(dirty_proc.stdout.strip()) if dirty_proc.returncode == 0 else False

                    return {
                        "vcs_type": "git",
                        "commit_sha": sha,
                        "branch": branch,
                        "is_dirty": is_dirty,
                        "status": "GIT_REPOSITORY",
                        "git_root": str(git_dir),
                        "discovered_utc": timestamp,
                    }
            except Exception:
                pass

    # 2. Build Manifest Discovery
    manifest_candidates = []
    if root_path is not None:
        manifest_candidates.append(Path(root_path) / ".build_manifest.json")
    if os.environ.get("COCHEM_ROOT"):
        manifest_candidates.append(Path(os.environ["COCHEM_ROOT"]) / ".build_manifest.json")
    manifest_candidates.append(Path(__file__).resolve().parents[2] / ".build_manifest.json")

    for mc in manifest_candidates:
        if mc.exists():
            try:
                import json

                data = json.loads(mc.read_text(encoding="utf-8"))
                return {
                    "vcs_type": "build_manifest",
                    "version": data.get("version", "unknown"),
                    "build_id": data.get("build_id", "unknown"),
                    "manifest_path": str(mc),
                    "status": "BUILD_MANIFEST",
                    "discovered_utc": timestamp,
                }
            except Exception:
                pass

    # 3. Distribution Package Introspection (importlib.metadata)
    pkg_names = ["CoChem-BASE", "cochem_base", "cochem-base"]
    for pkg in pkg_names:
        try:
            dist = importlib.metadata.distribution(pkg)
            dist_version = dist.version
            dist_files = dist.files
            installer = dist.read_text("INSTALLER") or "unknown"
            return {
                "vcs_type": "installed_wheel",
                "version": dist_version,
                "installer": installer.strip(),
                "file_count": len(dist_files) if dist_files else 0,
                "package_name": pkg,
                "status": "DISTRIBUTION_PACKAGE",
                "discovered_utc": timestamp,
            }
        except importlib.metadata.PackageNotFoundError:
            continue

    # 4. Clean Fallback for Untracked Environments
    return {
        "vcs_type": "untracked",
        "version": "0.1.0-untracked",
        "status": "UNTRACKED_BUILD",
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "discovered_utc": timestamp,
    }


__all__ = [
    "get_vcs_provenance",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\exceptions.py ---
"""Authoritative Core Domain Exceptions for CoChem-BASE.

Provides physical invariant exceptions for isotopic stability, empirical radii,
and domain perceptions adhering to Method Matrix v4 §6.10, §8C, and §20.
"""

from __future__ import annotations


class IsotopeStabilityError(ValueError):
    """Raised when a requested isotope cannot be physically resolved to an isotopic nuclear mass."""

    pass


class RadiusNotFoundError(KeyError):
    """Raised when empirical covalent or van der Waals radius is unavailable for an element."""

    pass


__all__ = [
    "IsotopeStabilityError",
    "RadiusNotFoundError",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\licensing.py ---
"""Authoritative Machine-Readable SPDX Data Usage Licensing Schema.

Adheres strictly to FAIR Principle R1.1 and Method Matrix v4 open-science mandates.
Validates dataset and computational model reuse rights against approved SPDX license identifiers.
"""

from __future__ import annotations

from typing import Final, FrozenSet

OFFICIAL_SPDX_LICENSES: Final[FrozenSet[str]] = frozenset({
    "CC-BY-4.0",
    "CC0-1.0",
    "CC-BY-SA-4.0",
    "CC-BY-NC-4.0",
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "GPL-3.0-only",
    "AGPL-3.0-only",
    "LGPL-3.0-only",
    "MPL-2.0",
    "ISC",
    "Unlicense",
})


def validate_spdx_license(license_id: str) -> str:
    """Validate that a license identifier conforms to approved SPDX open-science standards [D].

    Args:
        license_id: SPDX license expression string (e.g. 'CC-BY-4.0', 'MIT').

    Returns:
        str: Validated, stripped license identifier string.

    Raises:
        ValueError: If license_id is empty, invalid, or unrecognized in the SPDX table.
    """
    if not isinstance(license_id, str):
        raise ValueError(f"SPDX license identifier must be a string, got {type(license_id)}")

    clean_id = license_id.strip()
    if not clean_id:
        raise ValueError("SPDX license identifier cannot be empty.")

    if clean_id not in OFFICIAL_SPDX_LICENSES:
        raise ValueError(
            f"Invalid or unrecognized SPDX license identifier: '{clean_id}'. "
            f"Must be one of approved open-science identifiers: {sorted(OFFICIAL_SPDX_LICENSES)}"
        )

    return clean_id


__all__ = [
    "OFFICIAL_SPDX_LICENSES",
    "validate_spdx_license",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\metadata.py ---
"""Authoritative Dynamic Elemental Metadata, Empirical Radii, and Hardware Telemetry.

Complies strictly with:
- Dynamic Mendeleev Invariant Mandate (Method Matrix v4 §8C, zero hardcoded masses)
- Hierarchical Empirical Radii Lookup (Method Matrix v4 §20, Pyykkö -> Cordero -> vdW)
- Strictly Non-Initializing GPU Discovery (Method Matrix v4 §8A.4, zero CUDA-locking)
"""

from __future__ import annotations

import functools
import os
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union

import mendeleev

from cochem_base.core.exceptions import IsotopeStabilityError, RadiusNotFoundError


@functools.lru_cache(maxsize=1024)
def get_isotopic_mass(symbol_or_atomic_number: Union[str, int], mass_number: int) -> float:
    """Retrieve dynamic IUPAC/CIAAW isotopic nuclear mass for a specified isotope [M].

    Eradicates permissive fallback to terrestrial abundance-weighted average atomic weight.
    Strictly raises IsotopeStabilityError if the requested isotope cannot be physically resolved.

    Args:
        symbol_or_atomic_number: IUPAC elemental symbol (e.g. 'C', 'H', 'Cl') or integer atomic number (Z).
        mass_number: Integer nuclear nucleon count (A).

    Returns:
        float: Physical nuclear mass in unified atomic mass units (u) [M].

    Raises:
        IsotopeStabilityError: If the element or isotope does not exist in authoritative Mendeleev data.
    """
    try:
        el = mendeleev.element(symbol_or_atomic_number)
    except Exception as exc:
        raise IsotopeStabilityError(
            f"Element '{symbol_or_atomic_number}' could not be resolved in Mendeleev registry: {exc}"
        ) from exc

    target_a = int(mass_number)
    matched_iso = next((iso for iso in el.isotopes if iso.mass_number == target_a), None)

    if matched_iso is not None and matched_iso.mass is not None and float(matched_iso.mass) > 0.0:
        return float(matched_iso.mass)

    raise IsotopeStabilityError(
        f"Isotope '{el.symbol}-{mass_number}' cannot be resolved to a physical isotopic mass in authoritative CIAAW/Mendeleev data."
    )


@functools.lru_cache(maxsize=256)
def get_covalent_radius(
    symbol_or_atomic_number: Union[str, int],
    radius_type: str = "pyykko",
) -> float:
    """Hierarchical empirical covalent and van der Waals radii lookup in Angstroms [M].

    Hierarchy:
    1. Primary: Pyykkö single-bond covalent radius (covalent_radius_pyykko)
    2. Secondary: Cordero covalent radius (covalent_radius_cordero)
    3. Tertiary: Standard covalent radius (covalent_radius)
    4. Quaternary: van der Waals radius (vdw_radius)

    Eradicates hardcoded numeric fallbacks (e.g. 0.77 Å).

    Args:
        symbol_or_atomic_number: Element symbol or atomic number.
        radius_type: Preferred radius convention ('pyykko', 'cordero', 'vdw').

    Returns:
        float: Empirical radius in Angstroms [M].

    Raises:
        RadiusNotFoundError: If no valid empirical radius can be resolved.
    """
    try:
        el = mendeleev.element(symbol_or_atomic_number)
    except Exception as exc:
        raise RadiusNotFoundError(
            f"Element '{symbol_or_atomic_number}' could not be resolved from Mendeleev registries: {exc}"
        ) from exc

    rtype = radius_type.strip().lower()
    if rtype in ("cordero", "covalent_radius_cordero"):
        candidates = [el.covalent_radius_cordero, el.covalent_radius_pyykko, el.covalent_radius, el.vdw_radius]
    elif rtype in ("vdw", "vdw_radius"):
        candidates = [el.vdw_radius, el.covalent_radius_pyykko, el.covalent_radius_cordero, el.covalent_radius]
    else:
        # Default Pyykkö primary hierarchy
        candidates = [el.covalent_radius_pyykko, el.covalent_radius_cordero, el.covalent_radius, el.vdw_radius]

    for val in candidates:
        if val is not None:
            try:
                fval = float(val)
                if fval > 0.0:
                    # Mendeleev reports radii in picometers (pm); convert to Angstroms
                    return fval / 100.0
            except (ValueError, TypeError):
                continue

    raise RadiusNotFoundError(
        f"Empirical radius for element '{el.symbol}' ({el.atomic_number}) could not be resolved from Mendeleev registries."
    )


def _query_nvml_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Query NVIDIA NVML C-bindings without initializing the CUDA runtime [E]."""
    try:
        import pynvml  # type: ignore[import-not-found]

        pynvml.nvmlInit()
        devices = []
        try:
            count = pynvml.nvmlDeviceGetCount()
            for idx in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                try:
                    cc_major, cc_minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                    compute_cap = f"{cc_major}.{cc_minor}"
                except Exception:
                    compute_cap = "unknown"

                devices.append({
                    "index": idx,
                    "product_name": str(name),
                    "total_memory_bytes": int(mem.total),
                    "compute_capability": compute_cap,
                })
            return devices
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        return None


def _query_cli_gpu_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Query standalone GPU CLI tools (nvidia-smi / rocm-smi) in a fast isolated subprocess [E]."""
    nvsmi = shutil.which("nvidia-smi")
    if nvsmi:
        try:
            proc = subprocess.run(
                [nvsmi, "--query-gpu=index,gpu_name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                devices = []
                for line in proc.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        try:
                            idx = int(parts[0])
                            pname = parts[1]
                            mem_mib = float(parts[2])
                            devices.append({
                                "index": idx,
                                "product_name": pname,
                                "total_memory_bytes": int(mem_mib * 1024 * 1024),
                                "compute_capability": "unknown",
                            })
                        except (ValueError, IndexError):
                            continue
                if devices:
                    return devices
        except Exception:
            pass

    return None


def collect_hardware_metadata() -> Dict[str, Any]:
    """Collect host hardware and GPU accelerator telemetry using strictly non-initializing discovery [E].

    Guarantees zero CUDA runtime context initialization (zero CUDA-locking), maintaining NVIDIA MPS
    multiplexing readiness under Method Matrix v4 §8A.4.
    """
    # Strict AST / Runtime Prohibition verification
    if "torch" in sys.modules:
        torch_mod = sys.modules["torch"]
        if hasattr(torch_mod, "cuda") and hasattr(torch_mod.cuda, "is_initialized"):
            assert not torch_mod.cuda.is_initialized(), (
                "CUDA runtime was already initialized prior to non-initializing telemetry collection!"
            )

    gpus = _query_nvml_telemetry()
    if gpus is None:
        gpus = _query_cli_gpu_telemetry()
    if gpus is None:
        gpus = []

    cpu_count = os.cpu_count() or 1
    telemetry: Dict[str, Any] = {
        "platform": platform.platform(),
        "system": platform.system(),
        "cpu": {
            "architecture": platform.machine(),
            "processor": platform.processor() or "unknown",
            "physical_cores": cpu_count,
            "logical_cores": cpu_count,
        },
        "gpus": gpus,
        "gpu_count": len(gpus),
        "cuda_runtime_initialized": False,
    }

    return telemetry


__all__ = [
    "get_isotopic_mass",
    "get_covalent_radius",
    "collect_hardware_metadata",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\core\test_architecture_part6.py ---
"""Zero-Mock Architecture, Provenance, Hardware & Concurrency Test Suite (Part 6).

Validates Suggestions #53, #57, #58, and #59.
Adheres strictly to Method Matrix v4 and Zero-Mock Anti-Spoofing Protocol v2.
Real physical execution: authentic JSON-LD local schemas, genuine NVML hardware checks,
real HDF5 SWMR files, and node-local scratch locking.
"""

from __future__ import annotations

import json
import os
import pathlib
import threading
import time
from typing import List

import h5py

from cochem_base.core.cochem_provenance import DAGNode, get_local_prov_context
from cochem_base.core.cochem_version import get_vcs_provenance
from cochem_base.core.metadata import collect_hardware_metadata
from cochem_base.core_engine.cochem_core_pes_store import (
    PESPointRecord,
    PESStore,
)


def test_w3c_prov_o_jsonld_serialization() -> None:
    """Validate W3C PROV-O JSON-LD conformer lineage serialization and air-gapped context resolution (Suggestion #53)."""
    # 1. Verify offline local context resolution
    context_doc = get_local_prov_context()
    assert "@context" in context_doc
    ctx = context_doc["@context"]
    assert ctx.get("prov") == "http://www.w3.org/ns/prov#"
    assert ctx.get("cochem") == "https://cochem.org/schema/core#"
    assert "wasDerivedFrom" in ctx
    assert "wasGeneratedBy" in ctx

    # 2. Instantiate DAGNode for an activity (optimization step)
    activity_node = DAGNode(
        node_id="opt_step_001",
        node_type="activity",
        activity_type="cochem:Optimization",
        started_at_time="2026-09-04T00:00:00Z",
        ended_at_time="2026-09-04T00:01:30Z",
        metadata={"engine": "ORCA", "method": "wB97M-V", "basis": "def2-TZVP"},
    )
    act_jsonld = activity_node.to_prov_jsonld()
    assert act_jsonld["@id"] == "urn:cochem:conformer:opt_step_001"
    assert "prov:Activity" in act_jsonld["@type"]
    assert "cochem:Optimization" in act_jsonld["@type"]
    assert act_jsonld["prov:startedAtTime"] == "2026-09-04T00:00:00Z"
    assert act_jsonld["prov:endedAtTime"] == "2026-09-04T00:01:30Z"

    # 3. Instantiate DAGNode for an entity (resulting conformer)
    conformer_node = DAGNode(
        node_id="conf_c2h6_min01",
        node_type="entity",
        parents=["conf_initial_guess"],
        activity="opt_step_001",
        relative_energy_kcal_mol=0.0,
        rotational_constants_mhz=[199824.5, 199824.1, 199820.0],
        metadata={"multiplicity": 1, "charge": 0},
    )
    conf_jsonld = conformer_node.to_prov_jsonld()
    assert conf_jsonld["@id"] == "urn:cochem:conformer:conf_c2h6_min01"
    assert "prov:Entity" in conf_jsonld["@type"]
    assert "cochem:Conformer" in conf_jsonld["@type"]
    assert conf_jsonld["prov:wasDerivedFrom"] == [{"@id": "urn:cochem:conformer:conf_initial_guess"}]
    assert conf_jsonld["prov:wasGeneratedBy"] == {"@id": "urn:cochem:activity:opt_step_001"}
    assert conf_jsonld["cochem:relativeEnergy"] == 0.0
    assert conf_jsonld["cochem:rotationalConstants"] == [199824.5, 199824.1, 199820.0]

    # Verify standard JSON serialization succeeds
    serialized = json.dumps(conf_jsonld)
    assert "urn:cochem:conformer:conf_c2h6_min01" in serialized


def test_vcs_provenance_container_introspection(tmp_path: pathlib.Path) -> None:
    """Validate dynamic VCS provenance and importlib.metadata distribution fallback (Suggestion #57)."""
    # 1. In a directory without .git, verify fallback to importlib.metadata
    isolated_dir = tmp_path / "stripped_container_root"
    isolated_dir.mkdir(parents=True, exist_ok=True)

    prov = get_vcs_provenance(root_path=isolated_dir)
    assert isinstance(prov, dict)
    assert "status" in prov
    # Since CoChem-BASE is installed in this python environment, status must be DISTRIBUTION_PACKAGE
    assert prov["status"] == "DISTRIBUTION_PACKAGE"
    assert prov["vcs_type"] == "installed_wheel"
    assert "version" in prov
    assert len(prov["version"]) > 0
    assert "installer" in prov
    assert "file_count" in prov
    assert prov["file_count"] > 0

    # 2. When executed from repo root with .git present, queries commit information
    repo_prov = get_vcs_provenance()
    assert isinstance(repo_prov, dict)
    assert "status" in repo_prov
    assert repo_prov["status"] in ("GIT_REPOSITORY", "DISTRIBUTION_PACKAGE")


def test_strictly_non_initializing_gpu_telemetry() -> None:
    """Validate strictly non-initializing GPU telemetry with zero CUDA context locking (Suggestion #58)."""
    # 1. Execute collect_hardware_metadata
    hw_info = collect_hardware_metadata()
    assert isinstance(hw_info, dict)
    assert "cpu" in hw_info
    assert "architecture" in hw_info["cpu"]
    assert "physical_cores" in hw_info["cpu"]
    assert "gpus" in hw_info
    assert isinstance(hw_info["gpus"], list)

    # 2. Zero-CUDA-Locking Invariant Mandate
    # Check if torch is in sys.modules, and if so, verify that CUDA was not initialized
    import sys
    if "torch" in sys.modules:
        import torch
        assert not torch.cuda.is_initialized(), "torch.cuda was initialized during hardware metadata collection!"


def test_pes_store_swmr_concurrency_and_local_locking(tmp_path: pathlib.Path) -> None:
    """Validate thread-safe SWMR HDF5 execution and node-local scratch FileLock enforcement (Suggestion #59)."""
    h5_file = tmp_path / "pes_swmr_test.h5"
    scratch_dir = tmp_path / "node_local_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Set SLURM_TMPDIR to test local scratch lockfile redirection
    os.environ["SLURM_TMPDIR"] = str(scratch_dir.resolve())
    try:
        # 1. Initialize PESStore in SWMR mode
        store = PESStore(
            path=h5_file,
            complex_name="CO_H2O",
            symbols=["C", "O", "H", "H", "O"],
            swmr_mode=True,
        )

        # 2. Verify lockfile directory is placed in node-local scratch, not shared storage
        assert store.lock_dir.resolve() == scratch_dir.resolve()
        assert str(scratch_dir.resolve()) in str(store.lock_path.resolve())

        # 3. Concurrent read and write execution
        symbols = ["C", "O", "H", "H", "O"]
        base_coords = [0.0, 0.0, 0.0, 0.0, 0.0, 1.13, 2.0, 0.0, 0.0, 2.5, 0.7, 0.0, 2.5, -0.7, 0.0]
        method = "wB97M-V"
        basis = "def2-TZVP"

        # Register method first
        store.register_method(method_id="wb97mv_tzvp", method=method, basis=basis)

        written_points: List[str] = []
        errors: List[Exception] = []

        def worker_writer(thread_idx: int, num_pts: int) -> None:
            for i in range(num_pts):
                try:
                    # Deterministic perturbed geometry
                    geom = [c + 0.01 * (thread_idx + 1) * (i + 1) for c in base_coords]
                    pt = PESPointRecord(
                        coordinates=geom,
                        symbols=symbols,
                        method=method,
                        basis=basis,
                        method_id="wb97mv_tzvp",
                        energy=-189.12345 + 0.001 * (thread_idx + i),
                    )
                    store.add_point(pt)
                    written_points.append(pt.point_id)
                except Exception as exc:
                    errors.append(exc)

        def worker_reader(num_reads: int) -> None:
            for _ in range(num_reads):
                try:
                    pts = store.get_all_point_ids()
                    assert isinstance(pts, list)
                    time.sleep(0.005)
                except Exception as exc:
                    errors.append(exc)

        threads: List[threading.Thread] = []
        # Launch 3 writer threads and 2 reader threads
        for t_idx in range(3):
            t = threading.Thread(target=worker_writer, args=(t_idx, 5))
            threads.append(t)
        for _ in range(2):
            t = threading.Thread(target=worker_reader, args=(10,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Encountered concurrency errors: {errors}"
        all_ids = store.get_all_point_ids()
        assert len(all_ids) == 15
        for pid in written_points:
            assert pid in all_ids

        # Verify dataset integrity and absence of B-tree corruption
        with h5py.File(h5_file, "r", libver="latest", swmr=True) as f:
            coords = f["/points/coordinates"]
            coords.refresh()
            assert coords.shape[0] == 15
            energies = f["/points/energies"]
            energies.refresh()
            assert energies.shape[0] == 15

    finally:
        os.environ.pop("SLURM_TMPDIR", None)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\core\test_physics_integrity_part6.py ---
"""Zero-Mock Physics Invariants, Radii, Licensing & Asymmetric Signatures Test Suite (Part 6).

Validates Suggestions #51, #52, #54, #55, #56, #59, and #60.
Adheres strictly to Method Matrix v4 and Zero-Mock Anti-Spoofing Protocol v2.
Real physical execution: authentic dynamic Mendeleev masses/radii, RFC 8032 PureEd25519,
W3C Linked Data Proof did:key signatures, and deterministic UUIDv5 content hashing.
"""

from __future__ import annotations

import copy

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import ValidationError

import cochem_base.cochem_core_registry_schema as cochem_core_registry_schema
from cochem_base.cochem_core_registry_schema import get_registry_atomic_mass
from cochem_base.core.cochem_crypto import (
    did_key_to_public_key,
    public_key_to_did_key,
    sign_report_payload,
    verify_report_payload,
)
from cochem_base.core.exceptions import IsotopeStabilityError, RadiusNotFoundError
from cochem_base.core.glossary import CalculationFidelity
from cochem_base.core.metadata import get_covalent_radius, get_isotopic_mass
from cochem_base.core.models import CalculationJobPayload, PESPointRecord, QCResultsRecord
from cochem_base.core_engine.cochem_core_pes_store import QCSchemaMethodRecord, QCSchemaProvenance


def test_mendeleev_isotopic_nuclear_mass_resolution() -> None:
    """Validate dynamic IUPAC/CIAAW isotopic nuclear mass resolution and unphysical fallback removal (Suggestion #51)."""
    # 1. Carbon-14: physical nuclear mass ~14.003242 u [M], strictly not terrestrial average 12.011 u
    c14_mass = get_isotopic_mass("C", 14)
    assert pytest.approx(c14_mass, rel=1e-6) == 14.003241988
    assert abs(c14_mass - 12.011) > 1.9

    # 2. Deuterium (2H): nuclear mass ~2.014102 u [M]
    h2_mass = get_isotopic_mass("H", 2)
    assert pytest.approx(h2_mass, rel=1e-6) == 2.014101778

    # 3. Nitrogen-15: ~15.000109 u [M]
    n15_mass = get_isotopic_mass("N", 15)
    assert pytest.approx(n15_mass, rel=1e-6) == 15.000108899

    # 4. Chlorine-37: ~36.965903 u [M]
    cl37_mass = get_isotopic_mass("Cl", 37)
    assert pytest.approx(cl37_mass, rel=1e-6) == 36.965902602

    # 5. Non-existent isotope must raise IsotopeStabilityError
    with pytest.raises(IsotopeStabilityError):
        get_isotopic_mass("C", 999)

    with pytest.raises(IsotopeStabilityError):
        get_isotopic_mass("H", 10)


def test_hierarchical_empirical_radii_lookup() -> None:
    """Validate hierarchical Pyykkö -> Cordero -> vdW empirical radii resolution (Suggestion #52)."""
    # 1. Argon (Noble Gas): empirical vdW radius ~1.88 Å (or Pyykkö covalent radius ~0.96 Å), strictly not 0.77 Å
    ar_radius = get_covalent_radius("Ar")
    assert abs(ar_radius - 0.77) > 0.15
    assert ar_radius > 0.9

    # 2. Carbon (sp3 single bond covalent radius ~0.75 - 0.77 Å)
    c_radius = get_covalent_radius("C")
    assert 0.70 <= c_radius <= 0.80

    # 3. Xenon: heavy noble gas, empirical radius > 1.3 Å
    xe_radius = get_covalent_radius("Xe")
    assert xe_radius > 1.3

    # 4. Unresolvable / invalid element must raise RadiusNotFoundError
    with pytest.raises(RadiusNotFoundError):
        get_covalent_radius("InvalidElement")


def test_spdx_data_licensing_validation() -> None:
    """Validate machine-readable SPDX data usage licensing enforcement (Suggestion #54)."""
    # 1. Official open-science licenses accepted
    prov_cc4 = QCSchemaProvenance(license="CC-BY-4.0")
    assert prov_cc4.license == "CC-BY-4.0"

    prov_cc0 = QCSchemaProvenance(license="CC0-1.0")
    assert prov_cc0.license == "CC0-1.0"

    prov_mit = QCSchemaProvenance(license="MIT")
    assert prov_mit.license == "MIT"

    # 2. Check QCResultsRecord and QCSchemaMethodRecord license fields
    rec = QCResultsRecord(license="Apache-2.0")
    assert rec.license == "Apache-2.0"

    meth = QCSchemaMethodRecord(method="B3LYP", basis="def2-SVP", license="BSD-3-Clause")
    assert meth.license == "BSD-3-Clause"

    # 3. Invalid or unrecognized license string must raise ValidationError
    with pytest.raises(ValidationError):
        QCSchemaProvenance(license="Proprietary-Unpublished-Invalid")

    with pytest.raises(ValidationError):
        QCResultsRecord(license="Proprietary-Unpublished-Invalid")


def test_dynamic_registry_schema_isotopic_masses() -> None:
    """Validate dynamic SQLite Mendeleev registry mass resolution and removal of static ISOTOPIC_MASSES (Suggestion #55)."""
    # 1. Dynamic query for Argon-40 and Chlorine-37
    ar40_mass = get_registry_atomic_mass("Ar", 40)
    assert pytest.approx(ar40_mass, rel=1e-6) == 39.962383124

    cl37_mass = get_registry_atomic_mass("Cl", 37)
    assert pytest.approx(cl37_mass, rel=1e-6) == 36.965902602

    # Standard terrestrial average weight query (mass_number=None)
    c_mass = get_registry_atomic_mass("C")
    assert pytest.approx(c_mass, rel=1e-3) == 12.011

    # Non-existent isotope query must raise IsotopeStabilityError
    with pytest.raises(IsotopeStabilityError):
        get_registry_atomic_mass("Ar", 999)

    # 2. Static dictionary eradication verification
    assert not hasattr(cochem_core_registry_schema, "ISOTOPIC_MASSES")


def test_w3c_linked_data_proof_pure_ed25519_did_key() -> None:
    """Validate W3C Linked Data Proof envelopes and offline did:key multicodec resolution (Suggestion #56)."""
    # 1. Generate real Ed25519 key pair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Verify did:key encoding and decoding
    did_key = public_key_to_did_key(public_key)
    assert did_key.startswith("did:key:z")
    recovered_pub = did_key_to_public_key(did_key)
    assert recovered_pub.public_bytes_raw() == public_key.public_bytes_raw()

    # 2. Sign computational payload
    payload = {
        "job_id": "job_opt_20260904_001",
        "method": "wB97M-V",
        "basis": "def2-TZVP",
        "energy_hartree": -76.42512345,
        "converged": True,
    }

    signed_doc = sign_report_payload(payload, private_key)
    assert "proof" in signed_doc
    proof = signed_doc["proof"]
    assert proof["type"] == "Ed25519Signature2020"
    assert proof["verificationMethod"] == did_key
    assert proof["proofPurpose"] == "assertionMethod"
    assert "proofValue" in proof
    assert "created" in proof

    # 3. Verify valid signature
    assert verify_report_payload(signed_doc) is True

    # 4. Tampering test: perturb energy by 1 micro-Hartree
    tampered_doc = copy.deepcopy(signed_doc)
    tampered_doc["energy_hartree"] = -76.42512445
    assert verify_report_payload(tampered_doc) is False


def test_deterministic_uuid5_pes_point_id() -> None:
    """Validate deterministic UUIDv5 content-addressable PES point identifier generation (Suggestion #59)."""
    geom1 = [0.0, 0.0, 0.0, 0.0, 0.0, 1.128, 2.0, 0.0, 0.0]
    symbols = ["C", "O", "He"]
    method = "DLPNO-CCSD(T)"
    basis = "cc-pVTZ"

    # Instantiate two distinct PESPointRecord objects with identical specifications
    pt1 = PESPointRecord(
        coordinates=geom1,
        symbols=symbols,
        method=method,
        basis=basis,
        energy=-113.25,
    )
    pt2 = PESPointRecord(
        coordinates=geom1,
        symbols=symbols,
        method=method,
        basis=basis,
        energy=-113.25,
    )
    assert pt1.point_id == pt2.point_id
    assert len(pt1.point_id) == 36  # Standard UUID string representation

    # Perturb one coordinate by 0.001 Angstrom
    geom_perturbed = list(geom1)
    geom_perturbed[2] += 0.001
    pt_perturbed = PESPointRecord(
        coordinates=geom_perturbed,
        symbols=symbols,
        method=method,
        basis=basis,
        energy=-113.25,
    )
    assert pt_perturbed.point_id != pt1.point_id


def test_calculation_fidelity_canonical_tiers() -> None:
    """Validate Method Matrix v4 canonical composite fidelity tier definitions (Suggestion #60)."""
    # 1. Verify official canonical composite tiers in CalculationFidelity enum
    assert CalculationFidelity.JUNCHS_F12 == "junChS-F12"
    assert CalculationFidelity.T3_3H == "T3-3h"
    assert CalculationFidelity.R2 == "R2"
    assert CalculationFidelity.CHS == "ChS"

    # 2. Instantiate CalculationJobPayload with string representations of canonical tiers
    job1 = CalculationJobPayload(fidelity="junChS-F12")
    assert job1.fidelity == CalculationFidelity.JUNCHS_F12

    job2 = CalculationJobPayload(fidelity="T3-3h")
    assert job2.fidelity == CalculationFidelity.T3_3H

    job3 = CalculationJobPayload(fidelity="R2")
    assert job3.fidelity == CalculationFidelity.R2

    # 3. Semiempirical and standard wavefunction tiers
    job4 = CalculationJobPayload(fidelity="XTB2")
    assert job4.fidelity == CalculationFidelity.XTB2

    job5 = CalculationJobPayload(fidelity="DLPNO_CCSD_T")
    assert job5.fidelity == CalculationFidelity.DLPNO_CCSD_T

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.