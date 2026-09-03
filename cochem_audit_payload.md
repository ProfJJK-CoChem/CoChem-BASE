Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260901-suggestions\.in-progress\Perfected_SRS_Chunk_14_TOPOS_Chemical_Perception_Part_1_prompts.md.
Original prompt:
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous feature suite specified in Software Requirements Specification (SRS) Chunk 14: `TOPOS_Chemical_Perception_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev library mandate, and Method Matrix v4. Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must execute physically against authentic chemical topologies, genuine molecular structures, and physical constants.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Inspect the repository structure under `cochem/topos/` to identify existing graph primitives, `TopologyInput` abstractions, and testing conventions established in prior TOPOS modules.
2. **Implementation**: Implement all target modules specified below with strict Python 3.10+ PEP 484 type annotations, thread-safe persistence, and custom typed domain exceptions (`ToposPerceptionError`, `TautomerEnumerationTimeoutError`, `TautomerCombinatorialLimitExceededError`, `ValenceConservationError`, `InvalidTopologyInputError`, `TautomerCanonicalizationError`, `TautomerPersistenceError`, `TautomerStorageLockTimeoutError`, `QuantumChemistryHandshakeError`, `GhostAtomSanitizationError`).
3. **Physical Test Suite**: Write comprehensive, unmocked test suites covering each module under `tests/topos/test_topos_tautomer.py` with authentic chemical species and physical fixtures (e.g., acetylacetone `CC(=O)CC(=O)C`, 2-pyridone `c1cc[nH]c(=O)c1`, acetamidine `CC(=N)N`, glutaconic acid `OC(=O)CC=CC(=O)O`, vinylogous ester `COC(=O)C=CCO`, 4-methyl-1H-imidazole `Cc1c[nH]cn1`, and BSSE water dimer counterpoise complexes with ghost atoms).
4. **Physical Verification**: Execute the test suite using `run_command` in the terminal (`pytest tests/topos/test_topos_tautomer.py -v`). Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured execution report detailing all files created and modified on disk.

---

### MODULE SPECIFICATIONS

#### 1. [TOPOS] Pydantic v2 Domain Models & Exception Hierarchy
- **File Target**: `cochem/topos/tautomer.py` (or `cochem/topos/perception/tautomer.py`, exported in `cochem/topos/__init__.py`)
- **Domain Exceptions**:
  - `ToposPerceptionError(Exception)`: Base exception for chemical perception and tautomer failures.
  - `TautomerEnumerationTimeoutError(ToposPerceptionError)`: Raised when tautomer state space traversal exceeds execution timeout ceiling.
  - `TautomerCombinatorialLimitExceededError(ToposPerceptionError)`: Raised when generated tautomer states exceed configured bounds in 'raise' mode.
  - `ValenceConservationError(ToposPerceptionError)`: Raised when a prototropic transform violates octet or valency conservation.
  - `InvalidTopologyInputError(ToposPerceptionError)`: Raised when input molecular structure is unparseable or topologically malformed.
  - `TautomerCanonicalizationError(ToposPerceptionError)`: Raised when canonical tautomer selection or fixed-H InChIKey hashing fails.
  - `TautomerPersistenceError(ToposPerceptionError)`: Raised when HDF5 serialization or deserialization fails.
  - `TautomerStorageLockTimeoutError(ToposPerceptionError)`: Raised when acquiring cross-platform filelock exceeds timeout ceiling.
  - `QuantumChemistryHandshakeError(ToposPerceptionError)`: Raised when downstream 3D embedding or GFN2-xTB pre-filtering fails.
  - `GhostAtomSanitizationError(ToposPerceptionError)`: Raised when BSSE ghost atoms cannot be harmonized with topology contracts.
- **Pydantic v2 Data Models (Python 3.10+)**:
  - `TopologyInput`:
    - `molecule_id: str`: Unique alphanumeric identifier for the molecule.
    - `smiles: Optional[str] = None`: Input SMILES string.
    - `elements: List[str]`: Elemental symbols (minimum length 1).
    - `atomic_numbers: List[int]`: IUPAC atomic numbers $Z$ (minimum length 1).
    - `coordinates: Optional[List[Tuple[float, float, float]]] = None`: Cartesian 3D coordinates in Angstroms $(x, y, z)$.
    - `bonds: List[Tuple[int, int, float]] = Field(default_factory=list)`: Edges: `(idx_i, idx_j, order)`.
    - `formal_charges: List[int] = Field(default_factory=list)`: Formal charge per atom.
    - `masses: Optional[List[float]] = None`: Atomic masses dynamically queried via `mendeleev`.
    - `is_ghost: List[bool] = Field(default_factory=list)`: Mask identifying BSSE ghost atoms.
    - Validation: Enforce that at least one of `smiles`, `coordinates`, or explicit `bonds` is provided. Harmonize lengths across `elements`, `atomic_numbers`, `is_ghost`, and `formal_charges`. For ghost atoms ($Z = 0$ or `sym.upper() in {"GH", "BQ", "X"}`), auto-set `is_ghost[i] = True`.
  - `TautomerCandidate`:
    - `candidate_id: str`: Unique candidate hash.
    - `smiles: str`: Canonical SMILES of the tautomer.
    - `inchi_key: str`: Standard InChIKey (27 chars).
    - `fixed_h_inchi_key: str`: Fixed-H InChIKey (27 chars).
    - `canonical_score: float`: Patterson score (higher is more favorable).
    - `relative_energy_kcal_mol: Optional[float] = None`: Relative electronic energy from xTB.
    - `is_canonical: bool = False`: Flag indicating designated canonical tautomer.
    - `transform_depth: int`: Number of elementary prototropic shifts from parent topology ($ge 0$).
    - `transform_history: List[str] = Field(default_factory=list)`: Sequence of SMIRKS applied.
  - `TautomerEnumerationConfig`:
    - `max_tautomers: int = Field(default=500, ge=1, le=10000)`: Max unique tautomers before truncation.
    - `max_transform_depth: int = Field(default=6, ge=1, le=20)`: Max search depth from parent topology.
    - `timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0)`: Process-level timeout limit.
    - `energy_cutoff_kcal_mol: float = Field(default=15.0, ge=0.0)`: Thermodynamic exclusion ceiling.
    - `truncation_policy: Literal["raise", "truncate"] = "truncate"`: Behavior when limit reached.
  - `TautomerEnsemble`:
    - `parent_id: str`: Parent molecule identifier.
    - `canonical_tautomer_id: str`: ID of designated canonical tautomer.
    - `total_generated: int`: Total unique tautomers identified.
    - `candidates: List[TautomerCandidate]`: List of generated tautomer candidates.
    - `execution_duration_seconds: float`: Wall-clock runtime for enumeration.
    - Validation: Exactly one candidate must have `is_canonical = True`, matching `canonical_tautomer_id`.

#### 2. [TOPOS] Prototropic Shift Transform Rules & Chemical Perception
- **Requirement ID**: `REQ-TOPOS-014.1`
- **File Target**: `cochem/topos/tautomer.py`
- **Perception & Representation**:
  - Accept molecular topologies via SMILES, SDF, or Pydantic `TopologyInput` records.
  - For 2D graph/SMILES inputs: perceive implicit hydrogens, hybridization, formal valencies, and Kekulé/aromatic representations.
  - For 3D Cartesian coordinates lacking explicit bonds: reconstruct topology using Pyykkö relativistic covalent radii dynamically queried from `mendeleev`. Ghost atoms ($Z = 0$ or `is_ghost[i] == True`) are assigned $0.0\,\text{Å}$ radius without querying `mendeleev`.
- **Directional SMIRKS Transform Library**:
  - Explicit atom-mapping with migrating protons as terminal substituents to eliminate divalent bridging hydrogen graph representations:
    * **1,3-Prototropic Shifts**:
      - *Keto-Enol (Forward)*: `[O,S,Se,Te:1]=[#6:2]-[#6:3]-[#1:4]>>[#1:4]-[O,S,Se,Te:1]-[#6:2]=[#6:3]`
      - *Keto-Enol (Reverse)*: `[#1:4]-[O,S,Se,Te:1]-[#6:2]=[#6:3]>>[O,S,Se,Te:1]=[#6:2]-[#6:3]-[#1:4]`
      - *Lactam-Lactim / Amide-Imidic (Forward)*: `[O,S:1]=[#6:2]-[#7:3]-[#1:4]>>[#1:4]-[O,S:1]-[#6:2]=[#7:3]`
      - *Lactam-Lactim / Amide-Imidic (Reverse)*: `[#1:4]-[O,S:1]-[#6:2]=[#7:3]>>[O,S:1]=[#6:2]-[#7:3]-[#1:4]`
      - *Heteroaromatic Lactam-Lactim (Forward)*: `[O,S:1]=[c:2]-[n;H1:3]>>[#1:4]-[O,S:1]-[c:2]:[n:3]`
      - *Heteroaromatic Lactam-Lactim (Reverse)*: `[#1:4]-[O,S:1]-[c:2]:[n:3]>>[O,S:1]=[c:2]-[n:3]-[#1:4]`
      - *Amidine-Amidine (Forward)*: `[#7:1]=[#6:2]-[#7:3]-[#1:4]>>[#1:4]-[#7:1]-[#6:2]=[#7:3]`
      - *Amidine-Amidine (Reverse)*: `[#1:4]-[#7:1]-[#6:2]=[#7:3]>>[#7:1]=[#6:2]-[#7:3]-[#1:4]`
      - *Imine-Enamine (Forward)*: `[#7:1]=[#6:2]-[#6:3]-[#1:4]>>[#1:4]-[#7:1]-[#6:2]=[#6:3]`
      - *Imine-Enamine (Reverse)*: `[#1:4]-[#7:1]-[#6:2]=[#6:3]>>[#7:1]=[#6:2]-[#6:3]-[#1:4]`
      - *Nitroso-Oxime (Forward)*: `[O:1]=[#7:2]-[#6:3]-[#1:4]>>[#1:4]-[O:1]-[#7:2]=[#6:3]`
      - *Nitroso-Oxime (Reverse)*: `[#1:4]-[O:1]-[#7:2]=[#6:3]>>[O:1]=[#7:2]-[#6:3]-[#1:4]`
    * **1,5-Prototropic Shifts (Conjugated & Vinylogous Systems)**:
      - *Vinylogous Keto-Enol (Forward)*: `[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#6:5]-[#1:6]>>[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#6:5]`
      - *Vinylogous Keto-Enol (Reverse)*: `[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#6:5]>>[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#6:5]-[#1:6]`
      - *Vinylogous Amide / Imine (Forward)*: `[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#7:5]-[#1:6]>>[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#7:5]`
      - *Vinylogous Amide / Imine (Reverse)*: `[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#7:5]>>[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#7:5]-[#1:6]`
    * **Heterocyclic Annular Shifts**:
      - *1,3-Diaza Annular Shift*: `[#1:6]-[n:1]1~[c,n:2]~[n:3]~[c,n:4]~[c,n:5]1>>[n:1]1~[c,n:2]~[n:3](-[#1:6])~[c,n:4]~[c,n:5]1`
      - Ring Kekulization prior to aliphatic matching or any-bond queries; post-transform sanitization via `Chem.SanitizeMol`.
- **Graph Lifecycle Safeguards**:
  - Implicit hydrogens expanded via `Chem.AddHs(mol)` prior to transform application.
  - Re-evaluate stereochemical parity post-transform (`Chem.AssignStereochemistry(mol, cleanIt=True, force=True)`).
  - Enforce net formal charge conservation ($\sum q_i = Q_{\text{net}}$) and total hydrogen conservation ($\sum H_i = H_{\text{tot}}$). Raise `ValenceConservationError` if octet or valence bounds are violated.

#### 3. [TOPOS] Graph State Space Traversal & Combinatorial Safeguards
- **Requirement ID**: `REQ-TOPOS-014.2`
- **File Target**: `cochem/topos/tautomer.py`
- **BFS Exploration Engine**:
  - Execute bounded Breadth-First Search from root topology $T_0$.
  - State queue tracks `(mol, depth, history)`. Depth bounded by `max_transform_depth` (default 6).
  - Candidate set bounded by `max_tautomers` (default 500). If exceeded:
    - If `truncation_policy == "raise"`, raise `TautomerCombinatorialLimitExceededError`.
    - If `truncation_policy == "truncate"`, gracefully halt traversal and return current pool.
  - Worker subprocess isolation via `concurrent.futures.ProcessPoolExecutor` with hard timeout ceiling of `30.0` seconds. If timeout expires, cleanly terminate child process and raise `TautomerEnumerationTimeoutError`.

#### 4. [TOPOS] Canonicalization, Fixed-H InChIKey Hashing & Deduplication
- **Requirement ID**: `REQ-TOPOS-014.3`
- **File Target**: `cochem/topos/tautomer.py`
- **Deduplication Hashing**:
  - Compute canonical SMILES, standard InChIKey (`Chem.MolToInchiKey(mol)`), and fixed-H InChIKey (`Chem.MolToInchiKey(mol, options="-FixedH")`).
  - Fixed-H InChIKey (27 characters `XXXXXXXXXXXXXX-YYYYYYYYYY-Z`) serves as the definitive deduplication key. Redundant paths collapsing to the same fixed-H InChIKey retain the minimal transform depth.
- **Patterson Scoring & Canonical Designation**:
  - Calculate heuristic canonical score:
    - $+100$ per fully aromatic ring
    - $+50$ per keto/carbonyl group over enol (in non-phenolic contexts)
    - $+25$ per lactam over lactim group
    - $-50$ per aci-nitro group
    - $-100$ per isolated charge or zwitterionic separation
  - The candidate with the highest canonical score is flagged `is_canonical = True`. Tie-breaking: select candidate with the lexicographically smallest canonical SMILES.

#### 5. [TOPOS] Ghost-Atom (BSSE) Handling & Dynamic Mendeleev Mass Retrieval
- **Requirement ID**: `REQ-TOPOS-014.4`
- **File Target**: `cochem/topos/tautomer.py`
- **BSSE Ghost Handling**:
  - Ghost atoms ($Z = 0$ or symbols `Gh`, `Bq`, `X`) must be identified and masked in `is_ghost: List[bool]`.
  - Dynamic queries to `mendeleev.element(Z)` MUST be guarded:
    - If $Z = 0$ or `is_ghost[i] == True`, assign atomic mass strictly as $0.0\,\text{Da}$ and covalent radius strictly as $0.0\,\text{Å}$ without calling `mendeleev`.
    - For non-ghost atoms, query dynamic mass via `mendeleev.element(Z).mass`.
  - Ghost atoms are strictly excluded from donor/acceptor perception and SMIRKS reaction graphs.

#### 6. [TOPOS] Downstream Method Matrix v4 QM Handshake & Pre-Filtering
- **Requirement ID**: `REQ-TOPOS-014.5`
- **File Target**: `cochem/topos/tautomer.py`
- **QM Handshake Adapter**:
  - Decouple in-memory enumeration engine ($T_{\text{engine}}$) from QM compute runners.
  - Downstream adapter `filter_tautomers_thermodynamics`:
    - Generate initial 3D coordinates for each 2D tautomer topology using RDKit ETKDGv3 (`rdDistGeom.ETKDGv3()`).
    - Execute semi-empirical GFN2-xTB single-point or optimization/frequency runs (`xtb --opt --ohess` or CREST GOAT `! GOAT XTB2`, Method Matrix §9B.1–§9B.2).
    - Compute relative electronic energy $\Delta E_{\text{elec}} = E_{\text{elec}}(T_k) - E_{\text{elec}}(T_{\text{canonical}})$.
    - Flag or prune tautomers exceeding `energy_cutoff_kcal_mol` (default $15.0\,\text{kcal/mol}$).
    - For downstream DFT optimizations, enforce multi-stage integration grid tightening from `DEFGRID1` to `TightOpt TightSCF DEFGRID3` (Lebedev 590) per Method Matrix v4 §4.4.

#### 7. [TOPOS] Thread-Safe HDF5 Persistence & 6-Tier Concurrency Matrix
- **Requirement ID**: `REQ-TOPOS-014.6`
- **File Target**: `cochem/topos/tautomer.py`
- **HDF5 Storage Layout**:
  - Persist under `/tautomers/{molecule_id}/`.
  - Use explicit fixed-width UTF-8 datatypes:
    - `h5py.string_dtype(encoding='utf-8', length=256)` for SMILES
    - `h5py.string_dtype(encoding='utf-8', length=32)` for standard and fixed-H InChIKeys
    - `float64` for scores and energies
    - `int32` for transform depths
    - GZIP compression level 4 with chunking.
- **6-Tier Concurrency Matrix**:
  - Multi-process coordination: `filelock.FileLock(path.with_suffix(".h5.lock"), timeout=30.0)` across all tiers (Windows NTFS, macOS, Linux, Codespaces, GitHub Actions).
  - Intra-process multi-threading: Acquire a module-level `threading.Lock()` to prevent race conditions on non-threadsafe PyPI `h5py` binaries (`H5_HAVE_THREADSAFE=0`).
  - Tier 6 (HPC): Node-local NVMe scratch staging (`$SLURM_TMPDIR`), centralized worker aggregation.

---

### CORE PYTHON INTERFACE SIGNATURES

Implement the following public API signatures in `cochem/topos/tautomer.py` and export them in `cochem/topos/__init__.py`:

```python
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
import h5py
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToposPerceptionError(Exception):
    """Base exception for chemical perception and tautomer failures."""


class TautomerEnumerationTimeoutError(ToposPerceptionError):
    """Raised when tautomer state space traversal exceeds execution timeout ceiling."""


class TautomerCombinatorialLimitExceededError(ToposPerceptionError):
    """Raised when generated tautomer states exceed configured bounds in 'raise' mode."""


class ValenceConservationError(ToposPerceptionError):
    """Raised when a prototropic transform violates octet or valency conservation."""


class InvalidTopologyInputError(ToposPerceptionError):
    """Raised when input molecular structure is unparseable or topologically malformed."""


class TautomerCanonicalizationError(ToposPerceptionError):
    """Raised when canonical tautomer selection or fixed-H InChIKey hashing fails."""


class TautomerPersistenceError(ToposPerceptionError):
    """Raised when HDF5 serialization or deserialization fails."""


class TautomerStorageLockTimeoutError(ToposPerceptionError):
    """Raised when acquiring cross-platform filelock exceeds timeout ceiling."""


class QuantumChemistryHandshakeError(ToposPerceptionError):
    """Raised when downstream 3D embedding or GFN2-xTB pre-filtering fails."""


class GhostAtomSanitizationError(ToposPerceptionError):
    """Raised when BSSE ghost atoms cannot be harmonized with topology contracts."""


class TopologyInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    molecule_id: str = Field(..., description="Unique alphanumeric identifier for the molecule")
    smiles: Optional[str] = Field(default=None, description="Input SMILES string")
    elements: List[str] = Field(..., min_length=1, description="Elemental symbols")
    atomic_numbers: List[int] = Field(..., min_length=1, description="IUPAC atomic numbers Z")
    coordinates: Optional[List[Tuple[float, float, float]]] = Field(default=None, description="Cartesian 3D coordinates in Angstroms (x, y, z)")
    bonds: List[Tuple[int, int, float]] = Field(default_factory=list, description="Edges: (idx_i, idx_j, order)")
    formal_charges: List[int] = Field(default_factory=list, description="Formal charge per atom")
    masses: Optional[List[float]] = Field(default=None, description="Atomic masses dynamically queried via mendeleev")
    is_ghost: List[bool] = Field(default_factory=list, description="Mask identifying BSSE ghost atoms")

    @model_validator(mode="before")
    @classmethod
    def pre_validate_arrays_and_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        elements = data.get("elements", [])
        n_atoms = len(elements)
        atomic_numbers = data.get("atomic_numbers", [])

        if "is_ghost" not in data or not data["is_ghost"]:
            ghost_symbols = {"GH", "BQ", "X"}
            data["is_ghost"] = [
                (z == 0 or sym.upper() in ghost_symbols)
                for z, sym in zip(atomic_numbers, elements)
            ] if len(atomic_numbers) == n_atoms else [False] * n_atoms

        if "formal_charges" not in data or not data["formal_charges"]:
            data["formal_charges"] = [0] * n_atoms

        return data

    @model_validator(mode="after")
    def validate_integrity(self) -> "TopologyInput":
        n_atoms = len(self.elements)
        if not self.smiles and not self.coordinates and not self.bonds:
            raise ValueError("At least one of smiles, coordinates, or explicit bonds must be provided")
        if self.coordinates is not None and len(self.coordinates) != n_atoms:
            raise ValueError(f"coordinates length {len(self.coordinates)} != elements length {n_atoms}")
        if len(self.atomic_numbers) != n_atoms:
            raise ValueError(f"atomic_numbers length {len(self.atomic_numbers)} != elements length {n_atoms}")
        if len(self.is_ghost) != n_atoms:
            raise ValueError(f"is_ghost length {len(self.is_ghost)} != elements length {n_atoms}")
        if len(self.formal_charges) != n_atoms:
            raise ValueError(f"formal_charges length {len(self.formal_charges)} != elements length {n_atoms}")
        if self.masses is not None and len(self.masses) != n_atoms:
            raise ValueError(f"masses length {len(self.masses)} != elements length {n_atoms}")

        for idx_i, idx_j, order in self.bonds:
            if not (0 <= idx_i < n_atoms and 0 <= idx_j < n_atoms):
                raise ValueError(f"Bond ({idx_i}, {idx_j}) references out-of-bounds atom index for n_atoms={n_atoms}")
            if idx_i == idx_j:
                raise ValueError(f"Self-referential bond ({idx_i}, {idx_j}) detected")
            if order <= 0.0 or order > 4.0:
                raise ValueError(f"Invalid bond order {order} for bond ({idx_i}, {idx_j})")

        return self


class TautomerCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., description="Unique candidate hash")
    smiles: str = Field(..., min_length=1, description="Canonical SMILES of the tautomer")
    inchi_key: str = Field(..., min_length=27, max_length=27, description="Standard InChIKey (27 chars)")
    fixed_h_inchi_key: str = Field(..., min_length=27, max_length=27, description="Fixed-H InChIKey (27 chars)")
    canonical_score: float = Field(..., description="Patterson score (higher is more favorable)")
    relative_energy_kcal_mol: Optional[float] = Field(default=None, description="Relative electronic energy from xTB")
    is_canonical: bool = Field(default=False, description="Flag indicating highest-ranking canonical tautomer")
    transform_depth: int = Field(..., ge=0, description="Number of elementary prototropic shifts from parent")
    transform_history: List[str] = Field(default_factory=list, description="Sequence of SMIRKS applied")


class TautomerEnumerationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_tautomers: int = Field(default=500, ge=1, le=10000, description="Max unique tautomers before truncation")
    max_transform_depth: int = Field(default=6, ge=1, le=20, description="Max search depth from parent topology")
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0, description="Process-level timeout limit")
    energy_cutoff_kcal_mol: float = Field(default=15.0, ge=0.0, description="Thermodynamic exclusion ceiling")
    truncation_policy: Literal["raise", "truncate"] = Field(
        default="truncate",
        description="Behavior when max_tautomers limit is reached"
    )


class TautomerEnsemble(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_id: str = Field(..., description="Parent molecule identifier")
    canonical_tautomer_id: str = Field(..., description="ID of designated canonical tautomer")
    total_generated: int = Field(..., ge=1, description="Total unique tautomers identified")
    candidates: List[TautomerCandidate] = Field(..., min_length=1, description="List of generated tautomer candidates")
    execution_duration_seconds: float = Field(..., ge=0.0, description="Wall-clock runtime for enumeration")

    @model_validator(mode="after")
    def validate_ensemble_consistency(self) -> "TautomerEnsemble":
        if len(self.candidates) != self.total_generated:
            raise ValueError(f"Candidate count {len(self.candidates)} != total_generated {self.total_generated}")

        candidate_map = {c.candidate_id: c for c in self.candidates}
        if self.canonical_tautomer_id not in candidate_map:
            raise ValueError(f"canonical_tautomer_id '{self.canonical_tautomer_id}' not found in candidates")

        canonical_count = sum(1 for c in self.candidates if c.is_canonical)
        if canonical_count != 1:
            raise ValueError(f"Exactly one candidate must have is_canonical=True; found {canonical_count}")

        if not candidate_map[self.canonical_tautomer_id].is_canonical:
            raise ValueError("Candidate matching canonical_tautomer_id must have is_canonical=True")

        return self


def enumerate_tautomers(
    input_topology: TopologyInput,
    config: TautomerEnumerationConfig
) -> TautomerEnsemble:
    """Pure in-memory Tier 2 prototropic graph enumeration kernel."""


def filter_tautomers_thermodynamics(
    ensemble: TautomerEnsemble,
    config: TautomerEnumerationConfig,
    scratch_dir: Path
) -> TautomerEnsemble:
    """Downstream adapter: generates 3D ETKDGv3 conformers and filters via GFN2-xTB."""


def save_tautomer_ensemble_to_hdf5(
    ensemble: TautomerEnsemble,
    hdf5_path: Path
) -> Path:
    """Tier 3 persistence: serializes tautomer candidates and metadata into HDF5 archive."""


def load_tautomer_ensemble_from_hdf5(
    hdf5_path: Path,
    molecule_id: str
) -> TautomerEnsemble:
    """Tier 3 persistence: retrieves and reconstructs validated TautomerEnsemble from HDF5 archive."""
```

---

### PHYSICAL VERIFICATION TEST SUITE (`tests/topos/test_topos_tautomer.py`)

Implement the physical verification suite reproducing the following tests against genuine molecular structures:

```python
import concurrent.futures
from pathlib import Path
import h5py
import numpy as np
import pytest
from pydantic import ValidationError

from cochem.topos.tautomer import (
    GhostAtomSanitizationError,
    InvalidTopologyInputError,
    TautomerCandidate,
    TautomerCombinatorialLimitExceededError,
    TautomerEnsemble,
    TautomerEnumerationConfig,
    TautomerEnumerationTimeoutError,
    TopologyInput,
    ValenceConservationError,
    enumerate_tautomers,
    filter_tautomers_thermodynamics,
    load_tautomer_ensemble_from_hdf5,
    save_tautomer_ensemble_to_hdf5,
)


def test_1_3_prototropic_shifts():
    """
    REQ-TOPOS-014.1a: Verify 1,3-prototropic shifts across keto-enol, lactam-lactim, and amidine systems.
    Ensures net formal charge and total hydrogen count are strictly conserved.
    """
    # 1. Acetylacetone (keto-enol)
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens_acac = enumerate_tautomers(acac, config)
    assert ens_acac.total_generated >= 2
    smiles_pool = {c.smiles for c in ens_acac.candidates}
    # Enol form must be generated
    assert any("O" in s and "=" in s for s in smiles_pool)

    # 2. 2-Pyridone (lactam-lactim)
    pyridone = TopologyInput(
        molecule_id="2_pyridone",
        smiles="c1cc[nH]c(=O)c1",
        elements=["C", "C", "C", "N", "C", "O", "C"],
        atomic_numbers=[6, 6, 6, 7, 6, 8, 6],
    )
    ens_pyr = enumerate_tautomers(pyridone, config)
    assert ens_pyr.total_generated >= 2
    pyr_smiles = {c.smiles for c in ens_pyr.candidates}
    assert any("Oc1ccccn1" in s or "c1ccncc1O" in s or "n" in s for s in pyr_smiles)

    # 3. Acetamidine (amidine-amidine)
    acetamidine = TopologyInput(
        molecule_id="acetamidine",
        smiles="CC(=N)N",
        elements=["C", "C", "N", "N"],
        atomic_numbers=[6, 6, 7, 7],
    )
    ens_amd = enumerate_tautomers(acetamidine, config)
    assert ens_amd.total_generated >= 1
    for c in ens_amd.candidates:
        assert c.fixed_h_inchi_key is not None
        assert len(c.fixed_h_inchi_key) == 27


def test_1_5_prototropic_shifts():
    """
    REQ-TOPOS-014.1b: Verify 1,5-prototropic shifts across conjugated systems (glutaconic acid).
    """
    glutaconic = TopologyInput(
        molecule_id="glutaconic_acid",
        smiles="OC(=O)CC=CC(=O)O",
        elements=["O", "C", "O", "C", "C", "C", "C", "O", "O"],
        atomic_numbers=[8, 6, 8, 6, 6, 6, 6, 8, 8],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens_glut = enumerate_tautomers(glutaconic, config)
    assert ens_glut.total_generated >= 1
    # Net formal charge remains 0
    for cand in ens_glut.candidates:
        assert cand.transform_depth <= config.max_transform_depth


def test_bfs_traversal_combinatorial_limits_and_timeout():
    """
    REQ-TOPOS-014.2: Verify bounds on state space traversal, truncation policies, and process timeout.
    """
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    # Test max_tautomers truncation policy 'truncate'
    config_trunc = TautomerEnumerationConfig(max_tautomers=1, truncation_policy="truncate")
    ens_trunc = enumerate_tautomers(acac, config_trunc)
    assert ens_trunc.total_generated <= 1

    # Test max_tautomers truncation policy 'raise'
    config_raise = TautomerEnumerationConfig(max_tautomers=1, truncation_policy="raise")
    with pytest.raises(TautomerCombinatorialLimitExceededError):
        enumerate_tautomers(acac, config_raise)

    # Test timeout ceiling
    config_timeout = TautomerEnumerationConfig(timeout_seconds=0.0001)
    with pytest.raises(TautomerEnumerationTimeoutError):
        enumerate_tautomers(acac, config_timeout)


def test_deduplication_fixed_h_inchikey_and_canonicalization():
    """
    REQ-TOPOS-014.3: Verify deduplication via Fixed-H InChIKeys and Patterson scoring canonicalization.
    4-Methyl-1H-imidazole tautomers share standard InChIKey but diverge on fixed-H InChIKey.
    """
    # 4-methyl-1H-imidazole (Cc1c[nH]cn1)
    med = TopologyInput(
        molecule_id="4_methyl_imidazole",
        smiles="Cc1c[nH]cn1",
        elements=["C", "C", "C", "N", "C", "N"],
        atomic_numbers=[6, 6, 6, 7, 6, 7],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens = enumerate_tautomers(med, config)
    assert ens.total_generated >= 2

    # Standard InChIKeys match, Fixed-H InChIKeys diverge
    fixed_h_keys = {c.fixed_h_inchi_key for c in ens.candidates}
    assert len(fixed_h_keys) == ens.total_generated

    # Canonical selection check
    assert ens.canonical_tautomer_id is not None
    canonical_candidates = [c for c in ens.candidates if c.is_canonical]
    assert len(canonical_candidates) == 1
    assert canonical_candidates[0].candidate_id == ens.canonical_tautomer_id


def test_ghost_atom_bsse_exclusion():
    """
    REQ-TOPOS-014.4: Verify ghost atoms (Z=0, symbol 'Gh') are assigned 0.0 Da and 0.0 A
    without invoking mendeleev, and excluded from SMIRKS reaction graphs.
    """
    bsse_water = TopologyInput(
        molecule_id="bsse_water_dimer",
        smiles="O.[*]",
        elements=["O", "H", "H", "Gh"],
        atomic_numbers=[8, 1, 1, 0],
        is_ghost=[False, False, False, True],
    )
    assert bsse_water.is_ghost[3] is True
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(bsse_water, config)
    # Ghost atom did not cause crash, valid ensemble produced
    assert ens.total_generated >= 1


def test_qm_handshake_and_thermodynamic_filtering(tmp_path):
    """
    REQ-TOPOS-014.5: Verify 3D conformer generation (ETKDGv3) and thermodynamic pre-filtering adapter.
    """
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2, energy_cutoff_kcal_mol=15.0)
    ens = enumerate_tautomers(acac, config)

    filtered_ens = filter_tautomers_thermodynamics(ens, config, scratch_dir=tmp_path)
    assert filtered_ens.total_generated >= 1
    for c in filtered_ens.candidates:
        if c.relative_energy_kcal_mol is not None:
            assert c.relative_energy_kcal_mol <= config.energy_cutoff_kcal_mol + 1e-4


def test_hdf5_threadsafe_concurrency_persistence(tmp_path):
    """
    REQ-TOPOS-014.6: Verify thread-safe and process-safe HDF5 persistence under filelock.
    """
    h5_file = tmp_path / "tautomer_archive.h5"
    acac = TopologyInput(
        molecule_id="acac_persisted",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(acac, config)

    # Save to HDF5
    saved_path = save_tautomer_ensemble_to_hdf5(ens, h5_file)
    assert saved_path.exists()

    # Load from HDF5
    loaded_ens = load_tautomer_ensemble_from_hdf5(h5_file, molecule_id="acac_persisted")
    assert loaded_ens.parent_id == ens.parent_id
    assert loaded_ens.total_generated == ens.total_generated
    assert loaded_ens.canonical_tautomer_id == ens.canonical_tautomer_id

    # Verify fixed-width datatypes
    with h5py.File(h5_file, "r") as f:
        grp = f[f"/tautomers/{ens.parent_id}"]
        assert "smiles" in grp
        assert "fixed_h_inchi_key" in grp
        assert "canonical_score" in grp
        assert grp["smiles"].dtype.kind == "S" or grp["smiles"].dtype.metadata is not None
```

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate**:
   - Every function, transform, and test fixture must execute physically against real molecular data using RDKit C++ wrappers and Python algorithms.
   - Absolutely no `pass` stubs, `NotImplementedError`, empty functions, or synthetic mocked arrays (`np.zeros`, `np.ones`, etc.) in place of genuine computation.
2. **Dynamic Mendeleev Mandate**:
   - All non-ghost atomic masses and covalent radii must be queried dynamically via `mendeleev.element(Z)`.
   - Ghost/dummy atoms ($Z = 0$ or `is_ghost == True`) must be assigned $0.0\,\text{Da}$ and $0.0\,\text{Å}$ without calling `mendeleev`.
   - Hardcoded atomic mass constants, isotopic lookup tables, or manual CODATA updates are strictly forbidden.
3. **Tripartite Workspace Air-Gap Architecture**:
   - Partition workflow across three disjoint physical realms:
     - Tier 1: Domain & Schema Realm ($T_{\text{schema}}$): Ingests and validates immutable Pydantic `TopologyInput` records. Zero disk writes.
     - Tier 2: Pure Algorithmic Compute Engine ($T_{\text{engine}}$): In-memory BFS state traversal, SMIRKS transforms, and Patterson scoring inside an isolated worker subprocess. Zero disk writes, zero network sockets.
     - Tier 3: Persistence & Cache Realm ($T_{\text{persist}}$): Thread-safe HDF5 serialization under cross-platform `filelock` and `threading.Lock`.
4. **Compute Boundaries & CUDA-Lock Prevention**:
   - Tautomer graph search, SMIRKS matching, and topological hashing are strictly CPU-bound.
   - Process pool workers must initialize with `os.environ["CUDA_VISIBLE_DEVICES"] = ""` inside the child process only, preventing accidental GPU runtime context allocation.
5. **Thread-Safe HDF5 Persistence & 6-Tier Concurrency Matrix**:
   - Multi-process coordination across all tiers (Windows NTFS, macOS, Linux, Codespaces, GitHub Actions): `filelock.FileLock(path.with_suffix(".h5.lock"), timeout=30.0)` on advisory `.lock` files.
   - Intra-process multi-threading concurrency: Acquire an internal module-level `threading.Lock()` to prevent data races on non-threadsafe PyPI `h5py` binaries (`H5_HAVE_THREADSAFE=0`).
   - Tier 6 (HPC): Node-local NVMe scratch staging (`$SLURM_TMPDIR`), centralized worker aggregation.
6. **OS-Agnostic Dynamic Path Resolution**:
   - Dynamic path lookups via `pathlib.Path`:
     - Scratch: `pathlib.Path(os.environ.get("COCHEM_SCRATCH_DIR") or os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR") or Path.home() / ".cochem" / "scratch")`
     - Artifacts: `pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR") or Path.home() / ".cochem" / "artifacts")`

---

### ACTION PLAN FOR CODER

1. Implement `cochem/topos/tautomer.py` (and export in `cochem/topos/__init__.py`) containing:
   - Domain exception hierarchy: `ToposPerceptionError`, `TautomerEnumerationTimeoutError`, `TautomerCombinatorialLimitExceededError`, `ValenceConservationError`, `InvalidTopologyInputError`, `TautomerCanonicalizationError`, `TautomerPersistenceError`, `TautomerStorageLockTimeoutError`, `QuantumChemistryHandshakeError`, `GhostAtomSanitizationError`.
   - Pydantic v2 data models: `TopologyInput`, `TautomerCandidate`, `TautomerEnumerationConfig`, `TautomerEnsemble`.
   - Directional SMIRKS transform dictionary covering 1,3-prototropic, 1,5-prototropic, and heterocyclic annular shifts with explicit hydrogen matching.
   - Module-level worker helper `_cpu_worker_init` setting `CUDA_VISIBLE_DEVICES=""`.
   - `enumerate_tautomers`: In-memory BFS traversal bounded by `max_tautomers`, `max_transform_depth`, and `timeout_seconds` inside `ProcessPoolExecutor`. Computes canonical SMILES, standard InChIKeys, and fixed-H InChIKeys for deduplication. Patterson scoring for canonical tautomer designation.
   - `filter_tautomers_thermodynamics`: RDKit ETKDGv3 3D conformer generation, semi-empirical GFN2-xTB single point / optimization execution, relative energy $\Delta E_{\text{elec}}$ filtering against `energy_cutoff_kcal_mol`.
   - `save_tautomer_ensemble_to_hdf5` & `load_tautomer_ensemble_from_hdf5`: Thread-safe HDF5 serialization using fixed-width UTF-8 strings (`S256`, `S32`), chunking, GZIP compression, `filelock.FileLock`, and module-level `threading.Lock()`.
2. Implement physical unit test suite in `tests/topos/test_topos_tautomer.py` with all genuine chemical test fixtures (acetylacetone, 2-pyridone, acetamidine, glutaconic acid, 4-methyl-1H-imidazole, and BSSE water dimer with ghost atom).
3. Run the test suite via `run_command` (`pytest tests/topos/test_topos_tautomer.py -v`) and verify 100% pass rate.
4. Output the complete list of touched and created files in your final execution report.
I have invoked the `cochem-audit` subagent ([Conversation a3af9ebf-e12a-49d0-ace5-f87ca45ef0fd](conversation://a3af9ebf-e12a-49d0-ace5-f87ca45ef0fd)) to perform an adversarial audit on the chunked coding prompt for `SRS_Chunk_14_TOPOS_Chemical_Perception_Part_1.md`. Awaiting the auditor's formal certification.
I have updated the chunked prompt with all 5 adversarial corrections and submitted it to `cochem-audit` ([Conversation a3af9ebf-e12a-49d0-ace5-f87ca45ef0fd](conversation://a3af9ebf-e12a-49d0-ace5-f87ca45ef0fd)) for final verification and certification. Awaiting final audit verdict.
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous feature suite specified in Software Requirements Specification (SRS) Chunk 14: `TOPOS_Chemical_Perception_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev library mandate, and Method Matrix v4. Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must execute physically against authentic chemical topologies, genuine molecular structures, and physical constants.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Inspect the repository structure under `cochem/topos/` to identify existing graph primitives, `TopologyInput` abstractions, and testing conventions established in prior TOPOS modules.
2. **Implementation**: Implement all target modules specified below with strict Python 3.10+ PEP 484 type annotations, thread-safe persistence, and custom typed domain exceptions (`ToposPerceptionError`, `TautomerEnumerationTimeoutError`, `TautomerCombinatorialLimitExceededError`, `ValenceConservationError`, `InvalidTopologyInputError`, `TautomerCanonicalizationError`, `TautomerPersistenceError`, `TautomerStorageLockTimeoutError`, `QuantumChemistryHandshakeError`, `GhostAtomSanitizationError`).
3. **Physical Test Suite**: Write comprehensive, unmocked test suites covering each module under `tests/topos/test_topos_tautomer.py` with authentic chemical species and physical fixtures (e.g., acetylacetone `CC(=O)CC(=O)C`, 2-pyridone `c1cc[nH]c(=O)c1`, acetamidine `CC(=N)N`, glutaconic acid `OC(=O)CC=CC(=O)O`, vinylogous ester `COC(=O)C=CCO`, 4-methyl-1H-imidazole `Cc1c[nH]cn1`, 1H-1,2,3-triazole `c1cn[nH]n1`, and BSSE water dimer counterpoise complexes with ghost atoms).
4. **Physical Verification**: Execute the test suite using `run_command` in the terminal (`pytest tests/topos/test_topos_tautomer.py -v`). Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured execution report detailing all files created and modified on disk.

---

### MODULE SPECIFICATIONS

#### 1. [TOPOS] Pydantic v2 Domain Models & Exception Hierarchy
- **File Target**: `cochem/topos/tautomer.py` (or `cochem/topos/perception/tautomer.py`, exported in `cochem/topos/__init__.py`)
- **Domain Exceptions**:
  - `ToposPerceptionError(Exception)`: Base exception for chemical perception and tautomer failures.
  - `TautomerEnumerationTimeoutError(ToposPerceptionError)`: Raised when tautomer state space traversal exceeds execution timeout ceiling.
  - `TautomerCombinatorialLimitExceededError(ToposPerceptionError)`: Raised when generated tautomer states exceed configured bounds in 'raise' mode.
  - `ValenceConservationError(ToposPerceptionError)`: Raised when a prototropic transform violates octet or valency conservation.
  - `InvalidTopologyInputError(ToposPerceptionError)`: Raised when input molecular structure is unparseable or topologically malformed.
  - `TautomerCanonicalizationError(ToposPerceptionError)`: Raised when canonical tautomer selection or fixed-H InChIKey hashing fails.
  - `TautomerPersistenceError(ToposPerceptionError)`: Raised when HDF5 serialization or deserialization fails.
  - `TautomerStorageLockTimeoutError(ToposPerceptionError)`: Raised when acquiring cross-platform filelock exceeds timeout ceiling.
  - `QuantumChemistryHandshakeError(ToposPerceptionError)`: Raised when downstream 3D embedding or GFN2-xTB pre-filtering fails.
  - `GhostAtomSanitizationError(ToposPerceptionError)`: Raised when BSSE ghost atoms cannot be harmonized with topology contracts.
- **Pydantic v2 Data Models (Python 3.10+)**:
  - `TopologyInput`:
    - `molecule_id: str`: Unique alphanumeric identifier for the molecule.
    - `smiles: Optional[str] = None`: Input SMILES string.
    - `elements: List[str]`: Elemental symbols (minimum length 1).
    - `atomic_numbers: List[int]`: IUPAC atomic numbers $Z$ (minimum length 1).
    - `coordinates: Optional[List[Tuple[float, float, float]]] = None`: Cartesian 3D coordinates in Angstroms $(x, y, z)$.
    - `bonds: List[Tuple[int, int, float]] = Field(default_factory=list)`: Edges: `(idx_i, idx_j, order)`.
    - `formal_charges: List[int] = Field(default_factory=list)`: Formal charge per atom.
    - `masses: Optional[List[float]] = None`: Atomic masses dynamically queried via `mendeleev`.
    - `is_ghost: List[bool] = Field(default_factory=list)`: Mask identifying BSSE ghost atoms.
    - Validation: Enforce that at least one of `smiles`, `coordinates`, or explicit `bonds` is provided. Harmonize lengths across `elements`, `atomic_numbers`, `is_ghost`, and `formal_charges`. For ghost atoms ($Z = 0$ or `sym.upper() in {"GH", "BQ", "X"}`), auto-set `is_ghost[i] = True`.
  - `TautomerCandidate`:
    - `candidate_id: str`: Unique candidate hash.
    - `smiles: str`: Canonical SMILES of the tautomer.
    - `inchi_key: str`: Standard InChIKey (27 chars).
    - `fixed_h_inchi_key: str`: Fixed-H InChIKey (27 chars).
    - `canonical_score: float`: Patterson score (higher is more favorable).
    - `relative_energy_kcal_mol: Optional[float] = None`: Relative electronic energy from xTB.
    - `is_canonical: bool = False`: Flag indicating designated canonical tautomer.
    - `transform_depth: int`: Number of elementary prototropic shifts from parent topology ($ge 0$).
    - `transform_history: List[str] = Field(default_factory=list)`: Sequence of SMIRKS applied.
  - `TautomerEnumerationConfig`:
    - `max_tautomers: int = Field(default=500, ge=1, le=10000)`: Max unique tautomers before truncation.
    - `max_transform_depth: int = Field(default=6, ge=1, le=20)`: Max search depth from parent topology.
    - `timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)`: Process-level timeout limit in seconds (must permit short test limits).
    - `energy_cutoff_kcal_mol: float = Field(default=15.0, ge=0.0)`: Thermodynamic exclusion ceiling.
    - `truncation_policy: Literal["raise", "truncate"] = "truncate"`: Behavior when limit reached.
  - `TautomerEnsemble`:
    - `parent_id: str`: Parent molecule identifier.
    - `canonical_tautomer_id: str`: ID of designated canonical tautomer.
    - `total_generated: int`: Total unique tautomers identified.
    - `candidates: List[TautomerCandidate]`: List of generated tautomer candidates.
    - `execution_duration_seconds: float`: Wall-clock runtime for enumeration.
    - Validation: Exactly one candidate must have `is_canonical = True`, matching `canonical_tautomer_id`.

#### 2. [TOPOS] Prototropic Shift Transform Rules & Chemical Perception
- **Requirement ID**: `REQ-TOPOS-014.1`
- **File Target**: `cochem/topos/tautomer.py`
- **Perception & Representation**:
  - Accept molecular topologies via SMILES, SDF, or Pydantic `TopologyInput` records.
  - For 2D graph/SMILES inputs: perceive implicit hydrogens, hybridization, formal valencies, and Kekulé/aromatic representations.
  - For 3D Cartesian coordinates lacking explicit bonds: reconstruct topology using Pyykkö relativistic covalent radii dynamically queried from `mendeleev`. Note that `mendeleev.element(Z).covalent_radius_pyykko` returns values in picometers (pm); divide by 100.0 to convert to Ångströms (`r_angstrom = float(el.covalent_radius_pyykko) / 100.0`). Ghost atoms ($Z = 0$ or `is_ghost[i] == True`) are assigned $0.0\,\text{Å}$ radius without querying `mendeleev`.
- **Directional SMIRKS Transform Library**:
  - Explicit atom-mapping with migrating protons as terminal substituents to eliminate divalent bridging hydrogen graph representations:
    * **1,3-Prototropic Shifts**:
      - *Keto-Enol (Forward)*: `[O,S,Se,Te:1]=[#6:2]-[#6:3]-[#1:4]>>[#1:4]-[O,S,Se,Te:1]-[#6:2]=[#6:3]`
      - *Keto-Enol (Reverse)*: `[#1:4]-[O,S,Se,Te:1]-[#6:2]=[#6:3]>>[O,S,Se,Te:1]=[#6:2]-[#6:3]-[#1:4]`
      - *Lactam-Lactim / Amide-Imidic (Forward)*: `[O,S:1]=[#6:2]-[#7:3]-[#1:4]>>[#1:4]-[O,S:1]-[#6:2]=[#7:3]`
      - *Lactam-Lactim / Amide-Imidic (Reverse)*: `[#1:4]-[O,S:1]-[#6:2]=[#7:3]>>[O,S:1]=[#6:2]-[#7:3]-[#1:4]`
      - *Heteroaromatic Lactam-Lactim (Forward)*: `[O,S:1]=[c:2]:[n:3]-[#1:4]>>[#1:4]-[O,S:1]-[c:2]:[n:3]`
      - *Heteroaromatic Lactam-Lactim (Reverse)*: `[#1:4]-[O,S:1]-[c:2]:[n:3]>>[O,S:1]=[c:2]:[n:3]-[#1:4]`
      - *Amidine-Amidine (Forward)*: `[#7:1]=[#6:2]-[#7:3]-[#1:4]>>[#1:4]-[#7:1]-[#6:2]=[#7:3]`
      - *Amidine-Amidine (Reverse)*: `[#1:4]-[#7:1]-[#6:2]=[#7:3]>>[#7:1]=[#6:2]-[#7:3]-[#1:4]`
      - *Imine-Enamine (Forward)*: `[#7:1]=[#6:2]-[#6:3]-[#1:4]>>[#1:4]-[#7:1]-[#6:2]=[#6:3]`
      - *Imine-Enamine (Reverse)*: `[#1:4]-[#7:1]-[#6:2]=[#6:3]>>[#7:1]=[#6:2]-[#6:3]-[#1:4]`
      - *Nitroso-Oxime (Forward)*: `[O:1]=[#7:2]-[#6:3]-[#1:4]>>[#1:4]-[O:1]-[#7:2]=[#6:3]`
      - *Nitroso-Oxime (Reverse)*: `[#1:4]-[O:1]-[#7:2]=[#6:3]>>[O:1]-[#7:2]-[#6:3]-[#1:4]`
    * **1,5-Prototropic Shifts (Conjugated & Vinylogous Systems)**:
      - *Vinylogous Keto-Enol (Forward)*: `[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#6:5]-[#1:6]>>[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#6:5]`
      - *Vinylogous Keto-Enol (Reverse)*: `[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#6:5]>>[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#6:5]-[#1:6]`
      - *Vinylogous Amide / Imine (Forward)*: `[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#7:5]-[#1:6]>>[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#7:5]`
      - *Vinylogous Amide / Imine (Reverse)*: `[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#7:5]>>[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#7:5]-[#1:6]`
    * **Heterocyclic Annular Shifts**:
      - *1,3-Diaza Annular Shift*: `[#1:6]-[n:1]1:[c,n:2]:[n:3]:[c,n:4]:[c,n:5]1>>[n:1]1:[c,n:2]:[n:3](-[#1:6]):[c,n:4]:[c,n:5]1`
      - *1,2-Diaza Annular Shift*: `[#1:6]-[n:1]1:[n:2]:[c,n:3]:[c,n:4]:[c,n:5]1>>[n:1]1:[n:2](-[#1:6]):[c,n:3]:[c,n:4]:[c,n:5]1`
      - Ring Kekulization prior to aliphatic matching or any-bond queries; post-transform sanitization via `Chem.SanitizeMol`.
- **Graph Lifecycle Safeguards**:
  - Implicit hydrogens expanded via `Chem.AddHs(mol)` prior to transform application.
  - Re-evaluate stereochemical parity post-transform (`Chem.AssignStereochemistry(mol, cleanIt=True, force=True)`).
  - Enforce net formal charge conservation ($\sum q_i = Q_{\text{net}}$) and total hydrogen conservation ($\sum H_i = H_{\text{tot}}$). Raise `ValenceConservationError` if octet or valence bounds are violated.

#### 3. [TOPOS] Graph State Space Traversal & Combinatorial Safeguards
- **Requirement ID**: `REQ-TOPOS-014.2`
- **File Target**: `cochem/topos/tautomer.py`
- **BFS Exploration Engine**:
  - Execute bounded Breadth-First Search from root topology $T_0$.
  - State queue tracks `(mol, depth, history)`. Depth bounded by `max_transform_depth` (default 6).
  - Candidate set bounded by `max_tautomers` (default 500). If exceeded:
    - If `truncation_policy == "raise"`, raise `TautomerCombinatorialLimitExceededError`.
    - If `truncation_policy == "truncate"`, gracefully halt traversal and return current pool.
  - Worker subprocess isolation via `concurrent.futures.ProcessPoolExecutor` with hard timeout ceiling of `timeout_seconds`. If timeout expires, cleanly terminate child process and raise `TautomerEnumerationTimeoutError`.

#### 4. [TOPOS] Canonicalization, Fixed-H InChIKey Hashing & Deduplication
- **Requirement ID**: `REQ-TOPOS-014.3`
- **File Target**: `cochem/topos/tautomer.py`
- **Deduplication Hashing & Ghost Cleaning**:
  - Purge dummy/ghost atoms ($Z=0$, `[#0]`) via `Chem.DeleteSubstructs(mol, Chem.MolFromSmarts('[#0]'))` prior to computing InChI and InChIKeys, ensuring valid 27-character hashes without RDKit parser aborts.
  - Compute canonical SMILES, standard InChIKey (`Chem.MolToInchiKey(cleaned_mol)`), and fixed-H InChIKey (`Chem.MolToInchiKey(cleaned_mol, options="-FixedH")`).
  - Fixed-H InChIKey (27 characters `XXXXXXXXXXXXXX-YYYYYYYYYY-Z`) serves as the definitive deduplication key. Redundant paths collapsing to the same fixed-H InChIKey retain the minimal transform depth.
- **Patterson Scoring & Canonical Designation**:
  - Calculate heuristic canonical score:
    - $+100$ per fully aromatic ring
    - $+50$ per keto/carbonyl group over enol (in non-phenolic contexts)
    - $+25$ per lactam over lactim group
    - $-50$ per aci-nitro group
    - $-100$ per isolated charge or zwitterionic separation
  - The candidate with the highest canonical score is flagged `is_canonical = True`. Tie-breaking: select candidate with the lexicographically smallest canonical SMILES.

#### 5. [TOPOS] Ghost-Atom (BSSE) Handling & Dynamic Mendeleev Mass Retrieval
- **Requirement ID**: `REQ-TOPOS-014.4`
- **File Target**: `cochem/topos/tautomer.py`
- **BSSE Ghost Handling**:
  - Ghost atoms ($Z = 0$ or symbols `Gh`, `Bq`, `X`) must be identified and masked in `is_ghost: List[bool]`.
  - Dynamic queries to `mendeleev.element(Z)` MUST be guarded:
    - If $Z = 0$ or `is_ghost[i] == True`, assign atomic mass strictly as $0.0\,\text{Da}$ and covalent radius strictly as $0.0\,\text{Å}$ without calling `mendeleev`.
    - For non-ghost atoms, query dynamic mass via `mendeleev.element(Z).mass` and covalent radius via `float(mendeleev.element(Z).covalent_radius_pyykko) / 100.0`.
  - Ghost atoms are strictly excluded from donor/acceptor perception and SMIRKS reaction graphs.

#### 6. [TOPOS] Downstream Method Matrix v4 QM Handshake & Pre-Filtering
- **Requirement ID**: `REQ-TOPOS-014.5`
- **File Target**: `cochem/topos/tautomer.py`
- **QM Handshake Adapter**:
  - Decouple in-memory enumeration engine ($T_{\text{engine}}$) from QM compute runners.
  - Downstream adapter `filter_tautomers_thermodynamics`:
    - Generate initial 3D coordinates for each 2D tautomer topology using RDKit ETKDGv3 (`rdDistGeom.ETKDGv3()`).
    - Execute semi-empirical GFN2-xTB single-point or optimization/frequency runs (`xtb --opt --ohess` or CREST GOAT `! GOAT XTB2`, Method Matrix §9B.1–§9B.2).
    - Compute relative electronic energy $\Delta E_{\text{elec}} = E_{\text{elec}}(T_k) - E_{\text{elec}}(T_{\text{canonical}})$.
    - Flag or prune tautomers exceeding `energy_cutoff_kcal_mol` (default $15.0\,\text{kcal/mol}$).
    - For downstream DFT optimizations, enforce multi-stage integration grid tightening from `DEFGRID1` to `TightOpt TightSCF DEFGRID3` (Lebedev 590) per Method Matrix v4 §4.4.

#### 7. [TOPOS] Thread-Safe HDF5 Persistence & 6-Tier Concurrency Matrix
- **Requirement ID**: `REQ-TOPOS-014.6`
- **File Target**: `cochem/topos/tautomer.py`
- **HDF5 Storage Layout**:
  - Persist under `/tautomers/{molecule_id}/`.
  - Use explicit fixed-width UTF-8 datatypes:
    - `h5py.string_dtype(encoding='utf-8', length=256)` for SMILES
    - `h5py.string_dtype(encoding='utf-8', length=32)` for standard and fixed-H InChIKeys
    - `float64` for scores and energies
    - `int32` for transform depths
    - GZIP compression level 4 with chunking.
- **6-Tier Concurrency Matrix**:
  - Multi-process coordination: `filelock.FileLock(path.with_suffix(".h5.lock"), timeout=30.0)` across all tiers (Windows NTFS, macOS, Linux, Codespaces, GitHub Actions).
  - Intra-process multi-threading: Acquire a module-level `threading.Lock()` to prevent race conditions on non-threadsafe PyPI `h5py` binaries (`H5_HAVE_THREADSAFE=0`).
  - Tier 6 (HPC): Node-local NVMe scratch staging (`$SLURM_TMPDIR`), centralized worker aggregation.

---

### CORE PYTHON INTERFACE SIGNATURES

Implement the following public API signatures in `cochem/topos/tautomer.py` and export them in `cochem/topos/__init__.py`:

```python
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
import h5py
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToposPerceptionError(Exception):
    """Base exception for chemical perception and tautomer failures."""


class TautomerEnumerationTimeoutError(ToposPerceptionError):
    """Raised when tautomer state space traversal exceeds execution timeout ceiling."""


class TautomerCombinatorialLimitExceededError(ToposPerceptionError):
    """Raised when generated tautomer states exceed configured bounds in 'raise' mode."""


class ValenceConservationError(ToposPerceptionError):
    """Raised when a prototropic transform violates octet or valency conservation."""


class InvalidTopologyInputError(ToposPerceptionError):
    """Raised when input molecular structure is unparseable or topologically malformed."""


class TautomerCanonicalizationError(ToposPerceptionError):
    """Raised when canonical tautomer selection or fixed-H InChIKey hashing fails."""


class TautomerPersistenceError(ToposPerceptionError):
    """Raised when HDF5 serialization or deserialization fails."""


class TautomerStorageLockTimeoutError(ToposPerceptionError):
    """Raised when acquiring cross-platform filelock exceeds timeout ceiling."""


class QuantumChemistryHandshakeError(ToposPerceptionError):
    """Raised when downstream 3D embedding or GFN2-xTB pre-filtering fails."""


class GhostAtomSanitizationError(ToposPerceptionError):
    """Raised when BSSE ghost atoms cannot be harmonized with topology contracts."""


class TopologyInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    molecule_id: str = Field(..., description="Unique alphanumeric identifier for the molecule")
    smiles: Optional[str] = Field(default=None, description="Input SMILES string")
    elements: List[str] = Field(..., min_length=1, description="Elemental symbols")
    atomic_numbers: List[int] = Field(..., min_length=1, description="IUPAC atomic numbers Z")
    coordinates: Optional[List[Tuple[float, float, float]]] = Field(default=None, description="Cartesian 3D coordinates in Angstroms (x, y, z)")
    bonds: List[Tuple[int, int, float]] = Field(default_factory=list, description="Edges: (idx_i, idx_j, order)")
    formal_charges: List[int] = Field(default_factory=list, description="Formal charge per atom")
    masses: Optional[List[float]] = Field(default=None, description="Atomic masses dynamically queried via mendeleev")
    is_ghost: List[bool] = Field(default_factory=list, description="Mask identifying BSSE ghost atoms")

    @model_validator(mode="before")
    @classmethod
    def pre_validate_arrays_and_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        elements = data.get("elements", [])
        n_atoms = len(elements)
        atomic_numbers = data.get("atomic_numbers", [])

        if "is_ghost" not in data or not data["is_ghost"]:
            ghost_symbols = {"GH", "BQ", "X"}
            data["is_ghost"] = [
                (z == 0 or sym.upper() in ghost_symbols)
                for z, sym in zip(atomic_numbers, elements)
            ] if len(atomic_numbers) == n_atoms else [False] * n_atoms

        if "formal_charges" not in data or not data["formal_charges"]:
            data["formal_charges"] = [0] * n_atoms

        return data

    @model_validator(mode="after")
    def validate_integrity(self) -> "TopologyInput":
        n_atoms = len(self.elements)
        if not self.smiles and not self.coordinates and not self.bonds:
            raise ValueError("At least one of smiles, coordinates, or explicit bonds must be provided")
        if self.coordinates is not None and len(self.coordinates) != n_atoms:
            raise ValueError(f"coordinates length {len(self.coordinates)} != elements length {n_atoms}")
        if len(self.atomic_numbers) != n_atoms:
            raise ValueError(f"atomic_numbers length {len(self.atomic_numbers)} != elements length {n_atoms}")
        if len(self.is_ghost) != n_atoms:
            raise ValueError(f"is_ghost length {len(self.is_ghost)} != elements length {n_atoms}")
        if len(self.formal_charges) != n_atoms:
            raise ValueError(f"formal_charges length {len(self.formal_charges)} != elements length {n_atoms}")
        if self.masses is not None and len(self.masses) != n_atoms:
            raise ValueError(f"masses length {len(self.masses)} != elements length {n_atoms}")

        for idx_i, idx_j, order in self.bonds:
            if not (0 <= idx_i < n_atoms and 0 <= idx_j < n_atoms):
                raise ValueError(f"Bond ({idx_i}, {idx_j}) references out-of-bounds atom index for n_atoms={n_atoms}")
            if idx_i == idx_j:
                raise ValueError(f"Self-referential bond ({idx_i}, {idx_j}) detected")
            if order <= 0.0 or order > 4.0:
                raise ValueError(f"Invalid bond order {order} for bond ({idx_i}, {idx_j})")

        return self


class TautomerCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., description="Unique candidate hash")
    smiles: str = Field(..., min_length=1, description="Canonical SMILES of the tautomer")
    inchi_key: str = Field(..., min_length=27, max_length=27, description="Standard InChIKey (27 chars)")
    fixed_h_inchi_key: str = Field(..., min_length=27, max_length=27, description="Fixed-H InChIKey (27 chars)")
    canonical_score: float = Field(..., description="Patterson score (higher is more favorable)")
    relative_energy_kcal_mol: Optional[float] = Field(default=None, description="Relative electronic energy from xTB")
    is_canonical: bool = Field(default=False, description="Flag indicating highest-ranking canonical tautomer")
    transform_depth: int = Field(..., ge=0, description="Number of elementary prototropic shifts from parent")
    transform_history: List[str] = Field(default_factory=list, description="Sequence of SMIRKS applied")


class TautomerEnumerationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_tautomers: int = Field(default=500, ge=1, le=10000, description="Max unique tautomers before truncation")
    max_transform_depth: int = Field(default=6, ge=1, le=20, description="Max search depth from parent topology")
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0, description="Process-level timeout limit in seconds")
    energy_cutoff_kcal_mol: float = Field(default=15.0, ge=0.0, description="Thermodynamic exclusion ceiling")
    truncation_policy: Literal["raise", "truncate"] = Field(
        default="truncate",
        description="Behavior when max_tautomers limit is reached"
    )


class TautomerEnsemble(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_id: str = Field(..., description="Parent molecule identifier")
    canonical_tautomer_id: str = Field(..., description="ID of designated canonical tautomer")
    total_generated: int = Field(..., ge=1, description="Total unique tautomers identified")
    candidates: List[TautomerCandidate] = Field(..., min_length=1, description="List of generated tautomer candidates")
    execution_duration_seconds: float = Field(..., ge=0.0, description="Wall-clock runtime for enumeration")

    @model_validator(mode="after")
    def validate_ensemble_consistency(self) -> "TautomerEnsemble":
        if len(self.candidates) != self.total_generated:
            raise ValueError(f"Candidate count {len(self.candidates)} != total_generated {self.total_generated}")

        candidate_map = {c.candidate_id: c for c in self.candidates}
        if self.canonical_tautomer_id not in candidate_map:
            raise ValueError(f"canonical_tautomer_id '{self.canonical_tautomer_id}' not found in candidates")

        canonical_count = sum(1 for c in self.candidates if c.is_canonical)
        if canonical_count != 1:
            raise ValueError(f"Exactly one candidate must have is_canonical=True; found {canonical_count}")

        if not candidate_map[self.canonical_tautomer_id].is_canonical:
            raise ValueError("Candidate matching canonical_tautomer_id must have is_canonical=True")

        return self


def enumerate_tautomers(
    input_topology: TopologyInput,
    config: TautomerEnumerationConfig
) -> TautomerEnsemble:
    """Pure in-memory Tier 2 prototropic graph enumeration kernel."""


def filter_tautomers_thermodynamics(
    ensemble: TautomerEnsemble,
    config: TautomerEnumerationConfig,
    scratch_dir: Path
) -> TautomerEnsemble:
    """Downstream adapter: generates 3D ETKDGv3 conformers and filters via GFN2-xTB."""


def save_tautomer_ensemble_to_hdf5(
    ensemble: TautomerEnsemble,
    hdf5_path: Path
) -> Path:
    """Tier 3 persistence: serializes tautomer candidates and metadata into HDF5 archive."""


def load_tautomer_ensemble_from_hdf5(
    hdf5_path: Path,
    molecule_id: str
) -> TautomerEnsemble:
    """Tier 3 persistence: retrieves and reconstructs validated TautomerEnsemble from HDF5 archive."""
```

---

### PHYSICAL VERIFICATION TEST SUITE (`tests/topos/test_topos_tautomer.py`)

Implement the physical verification suite reproducing the following tests against genuine molecular structures:

```python
import concurrent.futures
from pathlib import Path
import h5py
import numpy as np
import pytest
from pydantic import ValidationError

from cochem.topos.tautomer import (
    GhostAtomSanitizationError,
    InvalidTopologyInputError,
    TautomerCandidate,
    TautomerCombinatorialLimitExceededError,
    TautomerEnsemble,
    TautomerEnumerationConfig,
    TautomerEnumerationTimeoutError,
    TopologyInput,
    ValenceConservationError,
    enumerate_tautomers,
    filter_tautomers_thermodynamics,
    load_tautomer_ensemble_from_hdf5,
    save_tautomer_ensemble_to_hdf5,
)


def test_1_3_prototropic_shifts():
    """
    REQ-TOPOS-014.1a: Verify 1,3-prototropic shifts across keto-enol, lactam-lactim, and amidine systems.
    Ensures net formal charge and total hydrogen count are strictly conserved.
    """
    # 1. Acetylacetone (keto-enol)
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens_acac = enumerate_tautomers(acac, config)
    assert ens_acac.total_generated >= 2
    smiles_pool = {c.smiles for c in ens_acac.candidates}
    # Enol form must be generated
    assert any("O" in s and "=" in s for s in smiles_pool)

    # 2. 2-Pyridone (heteroaromatic lactam-lactim)
    pyridone = TopologyInput(
        molecule_id="2_pyridone",
        smiles="c1cc[nH]c(=O)c1",
        elements=["C", "C", "C", "N", "C", "O", "C"],
        atomic_numbers=[6, 6, 6, 7, 6, 8, 6],
    )
    ens_pyr = enumerate_tautomers(pyridone, config)
    assert ens_pyr.total_generated >= 2
    pyr_smiles = {c.smiles for c in ens_pyr.candidates}
    assert any("Oc1ccccn1" in s or "c1ccncc1O" in s or "n" in s for s in pyr_smiles)

    # 3. Acetamidine (amidine-amidine)
    acetamidine = TopologyInput(
        molecule_id="acetamidine",
        smiles="CC(=N)N",
        elements=["C", "C", "N", "N"],
        atomic_numbers=[6, 6, 7, 7],
    )
    ens_amd = enumerate_tautomers(acetamidine, config)
    assert ens_amd.total_generated >= 1
    for c in ens_amd.candidates:
        assert c.fixed_h_inchi_key is not None
        assert len(c.fixed_h_inchi_key) == 27


def test_1_5_prototropic_shifts():
    """
    REQ-TOPOS-014.1b: Verify 1,5-prototropic shifts across conjugated systems (glutaconic acid).
    """
    glutaconic = TopologyInput(
        molecule_id="glutaconic_acid",
        smiles="OC(=O)CC=CC(=O)O",
        elements=["O", "C", "O", "C", "C", "C", "C", "O", "O"],
        atomic_numbers=[8, 6, 8, 6, 6, 6, 6, 8, 8],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens_glut = enumerate_tautomers(glutaconic, config)
    assert ens_glut.total_generated >= 1
    # Net formal charge remains 0
    for cand in ens_glut.candidates:
        assert cand.transform_depth <= config.max_transform_depth


def test_diaza_annular_shifts():
    """
    REQ-TOPOS-014.1c: Verify 1,2- and 1,3-diaza annular prototropic shifts across azoles.
    """
    # 1H-1,2,3-triazole (c1cn[nH]n1) undergoing 1,2- and 1,3-diaza shifts
    triazole = TopologyInput(
        molecule_id="1H_triazole",
        smiles="c1cn[nH]n1",
        elements=["C", "C", "N", "N", "N"],
        atomic_numbers=[6, 6, 7, 7, 7],
    )
    config = TautomerEnumerationConfig(max_tautomers=20, max_transform_depth=3)
    ens_triazole = enumerate_tautomers(triazole, config)
    assert ens_triazole.total_generated >= 2
    for c in ens_triazole.candidates:
        assert len(c.fixed_h_inchi_key) == 27


def test_bfs_traversal_combinatorial_limits_and_timeout():
    """
    REQ-TOPOS-014.2: Verify bounds on state space traversal, truncation policies, and process timeout.
    """
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    # Test max_tautomers truncation policy 'truncate'
    config_trunc = TautomerEnumerationConfig(max_tautomers=1, truncation_policy="truncate")
    ens_trunc = enumerate_tautomers(acac, config_trunc)
    assert ens_trunc.total_generated <= 1

    # Test max_tautomers truncation policy 'raise'
    config_raise = TautomerEnumerationConfig(max_tautomers=1, truncation_policy="raise")
    with pytest.raises(TautomerCombinatorialLimitExceededError):
        enumerate_tautomers(acac, config_raise)

    # Test timeout ceiling (using sub-second timeout enabled by gt=0.0)
    config_timeout = TautomerEnumerationConfig(timeout_seconds=0.0001)
    with pytest.raises(TautomerEnumerationTimeoutError):
        enumerate_tautomers(acac, config_timeout)


def test_deduplication_fixed_h_inchikey_and_canonicalization():
    """
    REQ-TOPOS-014.3: Verify deduplication via Fixed-H InChIKeys and Patterson scoring canonicalization.
    4-Methyl-1H-imidazole tautomers share standard InChIKey but diverge on fixed-H InChIKey.
    """
    # 4-methyl-1H-imidazole (Cc1c[nH]cn1)
    med = TopologyInput(
        molecule_id="4_methyl_imidazole",
        smiles="Cc1c[nH]cn1",
        elements=["C", "C", "C", "N", "C", "N"],
        atomic_numbers=[6, 6, 6, 7, 6, 7],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens = enumerate_tautomers(med, config)
    assert ens.total_generated >= 2

    # Standard InChIKeys match, Fixed-H InChIKeys diverge
    fixed_h_keys = {c.fixed_h_inchi_key for c in ens.candidates}
    assert len(fixed_h_keys) == ens.total_generated

    # Canonical selection check
    assert ens.canonical_tautomer_id is not None
    canonical_candidates = [c for c in ens.candidates if c.is_canonical]
    assert len(canonical_candidates) == 1
    assert canonical_candidates[0].candidate_id == ens.canonical_tautomer_id


def test_ghost_atom_bsse_exclusion():
    """
    REQ-TOPOS-014.4: Verify ghost atoms (Z=0, symbol 'Gh') are assigned 0.0 Da and 0.0 A
    without invoking mendeleev, and excluded from SMIRKS reaction graphs and InChI calculation.
    """
    bsse_water = TopologyInput(
        molecule_id="bsse_water_dimer",
        smiles="O.[*]",
        elements=["O", "H", "H", "Gh"],
        atomic_numbers=[8, 1, 1, 0],
        is_ghost=[False, False, False, True],
    )
    assert bsse_water.is_ghost[3] is True
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(bsse_water, config)
    # Ghost atom did not cause crash, valid ensemble produced with valid 27-char InChIKeys
    assert ens.total_generated >= 1
    for c in ens.candidates:
        assert len(c.inchi_key) == 27
        assert len(c.fixed_h_inchi_key) == 27


def test_qm_handshake_and_thermodynamic_filtering(tmp_path):
    """
    REQ-TOPOS-014.5: Verify 3D conformer generation (ETKDGv3) and thermodynamic pre-filtering adapter.
    """
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2, energy_cutoff_kcal_mol=15.0)
    ens = enumerate_tautomers(acac, config)

    filtered_ens = filter_tautomers_thermodynamics(ens, config, scratch_dir=tmp_path)
    assert filtered_ens.total_generated >= 1
    for c in filtered_ens.candidates:
        if c.relative_energy_kcal_mol is not None:
            assert c.relative_energy_kcal_mol <= config.energy_cutoff_kcal_mol + 1e-4


def test_hdf5_threadsafe_concurrency_persistence(tmp_path):
    """
    REQ-TOPOS-014.6: Verify thread-safe and process-safe HDF5 persistence under filelock.
    """
    h5_file = tmp_path / "tautomer_archive.h5"
    acac = TopologyInput(
        molecule_id="acac_persisted",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(acac, config)

    # Save to HDF5
    saved_path = save_tautomer_ensemble_to_hdf5(ens, h5_file)
    assert saved_path.exists()

    # Load from HDF5
    loaded_ens = load_tautomer_ensemble_from_hdf5(h5_file, molecule_id="acac_persisted")
    assert loaded_ens.parent_id == ens.parent_id
    assert loaded_ens.total_generated == ens.total_generated
    assert loaded_ens.canonical_tautomer_id == ens.canonical_tautomer_id

    # Verify fixed-width datatypes
    with h5py.File(h5_file, "r") as f:
        grp = f[f"/tautomers/{ens.parent_id}"]
        assert "smiles" in grp
        assert "fixed_h_inchi_key" in grp
        assert "canonical_score" in grp
        assert grp["smiles"].dtype.kind == "S" or grp["smiles"].dtype.metadata is not None
```

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate**:
   - Every function, transform, and test fixture must execute physically against real molecular data using RDKit C++ wrappers and Python algorithms.
   - Absolutely no `pass` stubs, `NotImplementedError`, empty functions, or synthetic mocked arrays (`np.zeros`, `np.ones`, etc.) in place of genuine computation.
2. **Dynamic Mendeleev Mandate**:
   - All non-ghost atomic masses and covalent radii must be queried dynamically via `mendeleev.element(Z)`.
   - Dynamic Pyykkö covalent radii must be converted from picometers to Ångströms: `r_angstrom = float(el.covalent_radius_pyykko) / 100.0`.
   - Ghost/dummy atoms ($Z = 0$ or `is_ghost == True`) must be assigned $0.0\,\text{Da}$ and $0.0\,\text{Å}$ without calling `mendeleev`.
   - Hardcoded atomic mass constants, isotopic lookup tables, or manual CODATA updates are strictly forbidden.
3. **Tripartite Workspace Air-Gap Architecture**:
   - Partition workflow across three disjoint physical realms:
     - Tier 1: Domain & Schema Realm ($T_{\text{schema}}$): Ingests and validates immutable Pydantic `TopologyInput` records. Zero disk writes.
     - Tier 2: Pure Algorithmic Compute Engine ($T_{\text{engine}}$): In-memory BFS state traversal, SMIRKS transforms, and Patterson scoring inside an isolated worker subprocess. Zero disk writes, zero network sockets.
     - Tier 3: Persistence & Cache Realm ($T_{\text{persist}}$): Thread-safe HDF5 serialization under cross-platform `filelock` and `threading.Lock`.
4. **Compute Boundaries & CUDA-Lock Prevention**:
   - Tautomer graph search, SMIRKS matching, and topological hashing are strictly CPU-bound.
   - Process pool workers must initialize with `os.environ["CUDA_VISIBLE_DEVICES"] = ""` inside the child process only, preventing accidental GPU runtime context allocation.
5. **Thread-Safe HDF5 Persistence & 6-Tier Concurrency Matrix**:
   - Multi-process coordination across all tiers (Windows NTFS, macOS, Linux, Codespaces, GitHub Actions): `filelock.FileLock(path.with_suffix(".h5.lock"), timeout=30.0)` on advisory `.lock` files.
   - Intra-process multi-threading concurrency: Acquire an internal module-level `threading.Lock()` to prevent data races on non-threadsafe PyPI `h5py` binaries (`H5_HAVE_THREADSAFE=0`).
   - Tier 6 (HPC): Node-local NVMe scratch staging (`$SLURM_TMPDIR`), centralized worker aggregation.
6. **OS-Agnostic Dynamic Path Resolution**:
   - Dynamic path lookups via `pathlib.Path`:
     - Scratch: `pathlib.Path(os.environ.get("COCHEM_SCRATCH_DIR") or os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR") or Path.home() / ".cochem" / "scratch")`
     - Artifacts: `pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR") or Path.home() / ".cochem" / "artifacts")`

---

### ACTION PLAN FOR CODER

1. Implement `cochem/topos/tautomer.py` (and export in `cochem/topos/__init__.py`) containing:
   - Domain exception hierarchy: `ToposPerceptionError`, `TautomerEnumerationTimeoutError`, `TautomerCombinatorialLimitExceededError`, `ValenceConservationError`, `InvalidTopologyInputError`, `TautomerCanonicalizationError`, `TautomerPersistenceError`, `TautomerStorageLockTimeoutError`, `QuantumChemistryHandshakeError`, `GhostAtomSanitizationError`.
   - Pydantic v2 data models: `TopologyInput`, `TautomerCandidate`, `TautomerEnumerationConfig`, `TautomerEnsemble`.
   - Directional SMIRKS transform dictionary covering 1,3-prototropic (including corrected heteroaromatic lactam-lactim), 1,5-prototropic, and heterocyclic annular shifts (including 1,2- and 1,3-diaza shifts) with explicit hydrogen matching.
   - Ghost atom stripping prior to InChI/InChIKey generation (`Chem.DeleteSubstructs(mol, Chem.MolFromSmarts('[#0]'))`).
   - Mendeleev unit conversion: `r_angstrom = float(el.covalent_radius_pyykko) / 100.0`.
   - Module-level worker helper `_cpu_worker_init` setting `CUDA_VISIBLE_DEVICES=""`.
   - `enumerate_tautomers`: In-memory BFS traversal bounded by `max_tautomers`, `max_transform_depth`, and `timeout_seconds` inside `ProcessPoolExecutor`. Computes canonical SMILES, standard InChIKeys, and fixed-H InChIKeys for deduplication. Patterson scoring for canonical tautomer designation.
   - `filter_tautomers_thermodynamics`: RDKit ETKDGv3 3D conformer generation, semi-empirical GFN2-xTB single point / optimization execution, relative energy $\Delta E_{\text{elec}}$ filtering against `energy_cutoff_kcal_mol`.
   - `save_tautomer_ensemble_to_hdf5` & `load_tautomer_ensemble_from_hdf5`: Thread-safe HDF5 serialization using fixed-width UTF-8 strings (`S256`, `S32`), chunking, GZIP compression, `filelock.FileLock`, and module-level `threading.Lock()`.
2. Implement physical unit test suite in `tests/topos/test_topos_tautomer.py` with all genuine chemical test fixtures (acetylacetone, 2-pyridone, acetamidine, glutaconic acid, 1H-1,2,3-triazole, 4-methyl-1H-imidazole, and BSSE water dimer with ghost atom).
3. Run the test suite via `run_command` (`pytest tests/topos/test_topos_tautomer.py -v`) and verify 100% pass rate.
4. Output the complete list of touched and created files in your final execution report.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\__init__.py ---
"""CoChem-TOPOS: Pure Topological Molecular Graph Theory and Geometry Subsystem."""

from __future__ import annotations

from cochem.topos.canonicalization import (
    TopologicalCanonicalizer,
    compute_node_invariant,
    compute_smallest_rings,
)
from cochem.topos.clash import ClashPair, GeometricClashDetector
from cochem.topos.coarse_grain import GraphCrusherConfig, crush_macromolecule
from cochem.topos.diff import compute_topology_diff
from cochem.topos.exceptions import (
    BondPerceptionError,
    ChiralityAssignmentError,
    CoChemError,
    CoChemToposException,
    FingerprintGenerationError,
    FragmentationError,
    GraphSparsificationError,
    IsomorphismMismatchError,
    IsotopeResolutionError,
    MalformedRecordError,
    ParsingAirGapError,
    PharmacophoreExtractionError,
    ResonanceEnumerationError,
    SolventBuilderError,
    StericClashError,
    SymmetryPerceptionError,
    TopologicalCanonicalizationError,
    TopologyDiffError,
    TopologyError,
    ToposError,
    BioisostereNotFoundError,
    CoordinationPerceptionError,
    GeometricPlausibilityError,
    PyMOLExportError,
    SanitizationError,
    ScaffoldMatchingError,
    TPSACalculationError,
    UnparameterizedAtomError,
)
from cochem.topos.fingerprint import (
    compute_dice_similarity,
    compute_tanimoto_similarity,
    generate_ecfp4_fingerprint,
)
from cochem.topos.forcefield import (
    assign_forcefield_parameters,
    geometric_combine,
    lorentz_berthelot_combine,
)
from cochem.topos.fragmentation import (
    fragment_by_brics,
    fragment_by_recap,
)
from cochem.topos.graph import TopologyGraph
from cochem.topos.io import (
    Mol2StreamReader,
    Mol2Writer,
    SDFStreamReader,
    SDFWriter,
)
from cochem.topos.isotopes import (
    IsotopeManager,
    IsotopeNodeSpec,
    get_isotope_info,
    get_isotope_mass,
)
from cochem.topos.models import (
    AttachmentSite,
    BondOrderEdge,
    BondPerceptionResult,
    ECFP4FingerprintPayload,
    ForceFieldAssignmentResult,
    MoleculeRecord,
    NonBondedParameter,
    SubgraphDeltaRecord,
    SynthonRecord,
    TopologyDelta,
    CoordinationCenter,
    CoordinationPerceptionResult,
    ExitVector,
    GeometricViolation,
    GeometryValidationResult,
    PolyhedronScore,
    PyMOLExportResult,
    ScaffoldHopResult,
    TopologySanitizationResult,
)
from cochem.topos.perception import perceive_bond_orders_from_xyz
from cochem.topos.pharmacophore import (
    PharmacophoreExtractor,
    PharmacophoreFeature,
    PharmacophoreFeatureSet,
)
from cochem.topos.resonance import (
    ResonanceEnsembleResult,
    ResonanceEnumerator,
    ResonanceStructure,
)
from cochem.topos.rings import (
    canonicalize_cycle,
    perceive_aromaticity,
    perceive_cycle_basis,
)
from cochem.topos.solvent import ExplicitSolventBuilder, SolventBox
from cochem.topos.sparsification import (
    GraphSparsifier,
    SparsifiedGraphResult,
    SparseEdge,
    load_pdb_topology,
)
from cochem.topos.stereochemistry import (
    assign_double_bond_stereo,
    assign_tetrahedral_chirality,
    compute_dihedral_angle,
)
from cochem.topos.symmetry import (
    TopologicalSymmetryAnalyzer,
    TopologicalSymmetryResult,
)
from cochem.topos.tpsa import (
    TPSACalculator,
    TPSAResult,
)
from cochem.topos.visualization import TOPOSpy3DmolWidget
from cochem.topos.scaffold_hopper import ScaffoldHopper
from cochem.topos.geometry_validation import DynamicBondDictionary
from cochem.topos.pymol_export import PyMOLExportEngine
from cochem.topos.metal_coordination import MetalCoordinationEngine
from cochem.topos.sanitizer import TopologySanitizer
from cochem.topos.alignment import (
    AirGapBoundaryViolationError,
    AlignedConformerResult,
    CollinearDegeneracyError,
    ConformerInput,
    DegenerateCoordinatesError,
    EnsembleAlignmentSummary,
    IncompatibleTopologyError,
    MCSAlignmentConfig,
    MCSConvergenceTimeoutError,
    StorageTier,
    ToposAlignmentError,
    align_conformers_by_mcs,
    cluster_ensemble_conformers,
    compute_kabsch_transformation,
    detect_concurrency_tier,
    persist_aligned_ensemble_h5,
)
from cochem.topos.tautomer import (
    GhostAtomSanitizationError,
    InvalidTopologyInputError,
    QuantumChemistryHandshakeError,
    TautomerCandidate,
    TautomerCanonicalizationError,
    TautomerCombinatorialLimitExceededError,
    TautomerEnsemble,
    TautomerEnumerationConfig,
    TautomerEnumerationTimeoutError,
    TautomerPersistenceError,
    TautomerStorageLockTimeoutError,
    TopologyInput,
    ToposPerceptionError,
    ValenceConservationError,
    enumerate_tautomers,
    filter_tautomers_thermodynamics,
    load_tautomer_ensemble_from_hdf5,
    save_tautomer_ensemble_to_hdf5,
)

__all__ = [
    "TopologyGraph",
    "GraphCrusherConfig",
    "crush_macromolecule",
    "perceive_cycle_basis",
    "perceive_aromaticity",
    "canonicalize_cycle",
    "assign_tetrahedral_chirality",
    "assign_double_bond_stereo",
    "compute_dihedral_angle",
    "TOPOSpy3DmolWidget",
    "GeometricClashDetector",
    "ClashPair",
    "CoChemError",
    "ToposError",
    "TopologyError",
    "StericClashError",
    "IsomorphismMismatchError",
    "ChiralityAssignmentError",
    "CoChemToposException",
    "SymmetryPerceptionError",
    "PharmacophoreExtractionError",
    "IsotopeResolutionError",
    "TPSACalculationError",
    "ResonanceEnumerationError",
    "GraphSparsificationError",
    "TopologicalSymmetryResult",
    "TopologicalSymmetryAnalyzer",
    "PharmacophoreFeature",
    "PharmacophoreFeatureSet",
    "PharmacophoreExtractor",
    "IsotopeNodeSpec",
    "IsotopeManager",
    "get_isotope_mass",
    "get_isotope_info",
    "TPSAResult",
    "TPSACalculator",
    "ResonanceStructure",
    "ResonanceEnsembleResult",
    "ResonanceEnumerator",
    "SparseEdge",
    "SparsifiedGraphResult",
    "GraphSparsifier",
    "load_pdb_topology",
    "SolventBuilderError",
    "TopologicalCanonicalizationError",
    "ExplicitSolventBuilder",
    "SolventBox",
    "TopologicalCanonicalizer",
    "compute_node_invariant",
    "compute_smallest_rings",
    # Chunk 11 additions
    "MalformedRecordError",
    "UnparameterizedAtomError",
    "BondPerceptionError",
    "ParsingAirGapError",
    "TopologyDiffError",
    "FragmentationError",
    "FingerprintGenerationError",
    "BondOrderEdge",
    "MoleculeRecord",
    "SubgraphDeltaRecord",
    "TopologyDelta",
    "AttachmentSite",
    "SynthonRecord",
    "NonBondedParameter",
    "ForceFieldAssignmentResult",
    "BondPerceptionResult",
    "ECFP4FingerprintPayload",
    "SDFStreamReader",
    "Mol2StreamReader",
    "SDFWriter",
    "Mol2Writer",
    "assign_forcefield_parameters",
    "lorentz_berthelot_combine",
    "geometric_combine",
    "fragment_by_brics",
    "fragment_by_recap",
    "perceive_bond_orders_from_xyz",
    "compute_topology_diff",
    "generate_ecfp4_fingerprint",
    "compute_tanimoto_similarity",
    "compute_dice_similarity",
    # Chunk 12 additions
    "BioisostereNotFoundError",
    "CoordinationPerceptionError",
    "GeometricPlausibilityError",
    "PyMOLExportError",
    "SanitizationError",
    "ScaffoldMatchingError",
    "ExitVector",
    "ScaffoldHopResult",
    "GeometricViolation",
    "GeometryValidationResult",
    "PyMOLExportResult",
    "PolyhedronScore",
    "CoordinationCenter",
    "CoordinationPerceptionResult",
    "TopologySanitizationResult",
    "ScaffoldHopper",
    "DynamicBondDictionary",
    "PyMOLExportEngine",
    "MetalCoordinationEngine",
    "TopologySanitizer",
    # Chunk 13 additions
    "ToposAlignmentError",
    "MCSConvergenceTimeoutError",
    "CollinearDegeneracyError",
    "DegenerateCoordinatesError",
    "IncompatibleTopologyError",
    "AirGapBoundaryViolationError",
    "ConformerInput",
    "MCSAlignmentConfig",
    "AlignedConformerResult",
    "EnsembleAlignmentSummary",
    "StorageTier",
    "detect_concurrency_tier",
    "compute_kabsch_transformation",
    "align_conformers_by_mcs",
    "cluster_ensemble_conformers",
    "persist_aligned_ensemble_h5",
    # Chunk 14 additions
    "ToposPerceptionError",
    "TautomerEnumerationTimeoutError",
    "TautomerCombinatorialLimitExceededError",
    "ValenceConservationError",
    "InvalidTopologyInputError",
    "TautomerCanonicalizationError",
    "TautomerPersistenceError",
    "TautomerStorageLockTimeoutError",
    "QuantumChemistryHandshakeError",
    "GhostAtomSanitizationError",
    "TopologyInput",
    "TautomerCandidate",
    "TautomerEnumerationConfig",
    "TautomerEnsemble",
    "enumerate_tautomers",
    "filter_tautomers_thermodynamics",
    "save_tautomer_ensemble_to_hdf5",
    "load_tautomer_ensemble_from_hdf5",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\exceptions.py ---
"""Domain-specific typed exceptions for CoChem-TOPOS Graph Theory and Topology subsystem."""

from __future__ import annotations


try:
    from cochem_base.exceptions import CoChemError  # type: ignore[import-not-found]
except ImportError:
    class CoChemError(Exception):  # type: ignore[no-redef]
        """Root fallback exception for CoChem errors."""

        def __init__(self, message: str = "") -> None:
            super().__init__(message)


class ToposError(CoChemError):
    """Base exception for all TOPOS operations."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TopologyError(ToposError):
    """Raised when graph topological invariants, contiguity, or conservation laws fail."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class StericClashError(ToposError):
    """Raised when geometric steric clashes are detected or physical radii are undefined."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class IsomorphismMismatchError(ToposError):
    """Raised when subgraph isomorphism matching fails or violates attribute constraints."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ChiralityAssignmentError(ToposError):
    """Raised when stereocenter assignment encounters degenerate, planar, or collinear geometries."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class CoChemToposException(TopologyError):
    """Root domain exception for CoChem-TOPOS Graph Theory operations."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class SymmetryPerceptionError(CoChemToposException):
    """Raised when symmetry perception or point group assignment fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class PharmacophoreExtractionError(CoChemToposException):
    """Raised when pharmacophore extraction encounters invalid chemical configurations."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class IsotopeResolutionError(CoChemToposException):
    """Raised when dynamic isotope query or mass resolution fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TPSACalculationError(CoChemToposException):
    """Raised when topological polar surface area calculation encounters unparameterized atoms."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ResonanceEnumerationError(CoChemToposException):
    """Raised when conjugated pi-system traversal or resonance structure generation fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class GraphSparsificationError(CoChemToposException):
    """Raised when graph sparsification or effective resistance solver fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class SolventBuilderError(CoChemToposException):
    """Raised when explicit solvent builder encounters invalid geometry, density, or bounding box."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TopologicalCanonicalizationError(CoChemToposException):
    """Raised when topological graph canonicalization or isomorphism invariant indexing fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class MalformedRecordError(ToposError):
    """Raised when input record syntax is corrupted or unparseable."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class UnparameterizedAtomError(ToposError):
    """Raised when an atom lacks forcefield parameters."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class BondPerceptionError(ToposError):
    """Raised when physical valences or bond orders cannot be resolved."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ParsingAirGapError(ToposError):
    """Raised when a parser worker process exceeds memory or execution time limits."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TopologyDiffError(ToposError):
    """Raised when MCS graph diffing fails to resolve."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class FragmentationError(ToposError):
    """Raised when retrosynthetic fragmentation or valence checking fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class FingerprintGenerationError(ToposError):
    """Raised when circular fingerprint generation fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ScaffoldMatchingError(ToposError):
    """Raised when target scaffold substructure cannot be mapped onto input molecule."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class BioisostereNotFoundError(ToposError):
    """Raised when no geometrically viable bioisostere satisfies exit-vector tolerances."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class GeometricPlausibilityError(ToposError):
    """Raised when 3D geometry exhibits critical steric clashes or unphysical valence strains."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class PyMOLExportError(ToposError):
    """Raised when .pse session or fallback .pml export fails to serialize."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class CoordinationPerceptionError(ToposError):
    """Raised when metal coordination polyhedra cannot be perceived or are heavily distorted."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class SanitizationError(ToposError):
    """Raised when charge neutralization violates octet rules or fragments essential complexes."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ToposAlignmentError(ToposError):
    """Base exception for topology alignment failures."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class MCSConvergenceTimeoutError(ToposAlignmentError):
    """Raised when MCS graph search exceeds timeout ceiling or is canceled."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class CollinearDegeneracyError(ToposAlignmentError):
    """Raised when atomic coordinates exhibit collinear rank-deficiency in SVD."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class DegenerateCoordinatesError(ToposAlignmentError):
    """Raised when atomic coordinates exhibit point-degeneracy."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class IncompatibleTopologyError(ToposAlignmentError):
    """Raised when molecules share insufficient overlapping substructure (N_MCS < 3)."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class AirGapBoundaryViolationError(ToposAlignmentError):
    """Raised when persistent archive paths resolve outside the designated T_store realm."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


# Chunk 14 Domain Exceptions
from cochem.topos.tautomer import (
    GhostAtomSanitizationError,
    InvalidTopologyInputError,
    QuantumChemistryHandshakeError,
    TautomerCanonicalizationError,
    TautomerCombinatorialLimitExceededError,
    TautomerEnumerationTimeoutError,
    TautomerPersistenceError,
    TautomerStorageLockTimeoutError,
    ToposPerceptionError,
    ValenceConservationError,
)


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_topos_alignment.py ---
"""Physical Verification Test Suite for CoChem-TOPOS Alignment Part 1.

Verifies chiral enantiomer reflection parity guards, collinear rank-deficiency,
coplanar coordinate stabilization, BSSE ghost-atom exclusion, Pydantic validation,
numerical degeneracy safeguards, MCS timeouts, ensemble clustering, and HDF5 persistence [M][D].
"""

from __future__ import annotations

import os
from pathlib import Path

import h5py
import numpy as np
from pydantic import ValidationError
import pytest

from cochem.topos.alignment import (
    AirGapBoundaryViolationError,
    AlignedConformerResult,
    CollinearDegeneracyError,
    ConformerInput,
    DegenerateCoordinatesError,
    EnsembleAlignmentSummary,
    IncompatibleTopologyError,
    MCSAlignmentConfig,
    MCSConvergenceTimeoutError,
    StorageTier,
    align_conformers_by_mcs,
    cluster_ensemble_conformers,
    compute_kabsch_transformation,
    detect_concurrency_tier,
    persist_aligned_ensemble_h5,
)


def test_kabsch_chiral_enantiomer_reflection_guard():
    """REQ-TOPOS-013.3 & REQ-TOPOS-013.4: Verify that Kabsch alignment between chiral enantiomers

    enforces proper rotation det(R) = +1.0 via parity correction factor d = -1, preventing coordinate inversion.
    """
    coords_l = np.array(
        [
            [-0.432, 1.254, -0.428],  # N
            [0.000, 0.000, 0.354],  # CA
            [1.520, 0.000, 0.354],  # C
            [2.145, 1.050, 0.354],  # O
            [-0.534, -1.242, -0.354],  # CB
        ],
        dtype=np.float64,
    )

    coords_d = coords_l.copy()
    coords_d[:, 2] *= -1.0

    r_rot, t_trans, rmsd = compute_kabsch_transformation(coords_d, coords_l)

    assert np.allclose(r_rot.T @ r_rot, np.eye(3), atol=1e-5), "Rotation matrix must satisfy R.T @ R = I"
    assert np.isclose(np.linalg.det(r_rot), 1.0, atol=1e-5), f"Improper rotation detected: det(R) = {np.linalg.det(r_rot)}"
    assert rmsd > 0.1, "Enantiomer alignment must retain non-zero RMSD under proper SO(3) rotation"


def test_collinear_degeneracy_detection():
    """REQ-TOPOS-013.3: Verify that collinear coordinates (e.g., linear acetylene C2H2)

    trigger CollinearDegeneracyError due to singular value condition ratio sigma_2 / sigma_1 < 1e-7.
    """
    acetylene_coords = np.array(
        [
            [0.0, 0.0, -1.665],  # H1
            [0.0, 0.0, -0.601],  # C1
            [0.0, 0.0, 0.601],  # C2
            [0.0, 0.0, 1.665],  # H2
        ],
        dtype=np.float64,
    )

    rotated_coords = acetylene_coords @ np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.float64)

    with pytest.raises(CollinearDegeneracyError) as exc_info:
        compute_kabsch_transformation(rotated_coords, acetylene_coords)
    assert "collinear" in str(exc_info.value).lower()


def test_coplanar_coordinates_stabilization():
    """REQ-TOPOS-013.3: Verify that coplanar coordinates (benzene C6 heavy atoms in xy-plane)

    are successfully stabilized via right-handed cross-product basis completion without degeneracy failure.
    """
    angles = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    r_cc = 1.397
    benzene_c = np.column_stack([r_cc * np.cos(angles), r_cc * np.sin(angles), np.zeros(6)])

    theta = np.pi / 4.0
    r_z = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0.0],
            [np.sin(theta), np.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    rotated_benzene = benzene_c @ r_z.T + np.array([1.5, -2.0, 0.0])

    r_rot, t_trans, rmsd = compute_kabsch_transformation(rotated_benzene, benzene_c)
    assert np.allclose(r_rot.T @ r_rot, np.eye(3), atol=1e-5)
    assert np.isclose(np.linalg.det(r_rot), 1.0, atol=1e-5)
    assert np.isclose(rmsd, 0.0, atol=1e-5)


def test_bsse_ghost_atom_exclusion_and_mass():
    """REQ-TOPOS-013.1 & REQ-TOPOS-013.2: Verify that BSSE counterpoise complexes with ghost atoms (Z=0)

    assign zero mass without throwing Mendeleev ValueError, and are excluded from alignment calculations.
    """
    target = ConformerInput(
        conformer_id="bsse_dimer_conf_1",
        elements=["O", "H", "H", "Gh", "Gh", "Gh"],
        atomic_numbers=[8, 1, 1, 0, 0, 0],
        coordinates=[
            (0.000, 0.000, 0.117),
            (0.000, 0.757, -0.469),
            (0.000, -0.757, -0.469),
            (2.800, 0.000, 0.117),
            (2.800, 0.757, -0.469),
            (2.800, -0.757, -0.469),
        ],
        is_ghost=[False, False, False, True, True, True],
    )
    assert len(target.is_ghost) == 6
    assert target.is_ghost[3] is True
    masses = target.get_dynamic_masses()
    assert len(masses) == 6
    assert masses[0] > 15.0  # Oxygen
    assert masses[3] == 0.0  # Ghost atom


def test_pydantic_validation_guards():
    """Verify that Pydantic v2 data models reject empty coordinate lists, non-orthogonal rotation matrices,

    and asymmetric pairwise RMSD matrices.
    """
    with pytest.raises(ValidationError):
        ConformerInput(
            conformer_id="invalid_conf_01",
            elements=["C", "C", "C"],
            atomic_numbers=[6, 6, 6],
            coordinates=[],
        )

    non_orthogonal_mat = [[2.0, 0.0, 0.0], [0.0, 0.5, 0.0], [0.0, 0.0, 1.0]]
    with pytest.raises(ValidationError):
        AlignedConformerResult(
            conformer_id="conf_01",
            reference_id="ref_01",
            rmsd_angstrom=0.15,
            rotation_matrix=non_orthogonal_mat,
            translation_vector=[0.0, 0.0, 0.0],
            aligned_coordinates=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            atom_mapping={0: 0, 1: 1, 2: 2},
            execution_duration_seconds=0.012,
        )

    with pytest.raises(ValidationError):
        EnsembleAlignmentSummary(
            ensemble_id="ens_01",
            reference_id="ref_01",
            total_conformers=2,
            aligned_conformers=[],
            pairwise_rmsd_matrix=[[0.0, 0.35], [0.10, 0.0]],
        )


def test_point_degeneracy_error():
    """REQ-TOPOS-013.3: Verify that point-collapsed coordinates raise DegenerateCoordinatesError."""
    point_coords = np.zeros((4, 3), dtype=np.float64)
    ref_coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    with pytest.raises(DegenerateCoordinatesError):
        compute_kabsch_transformation(point_coords, ref_coords)


def test_incompatible_topology_atom_count_error():
    """REQ-TOPOS-013.1: Verify IncompatibleTopologyError when overlapping atom count N_MCS < 3."""
    target = ConformerInput(
        conformer_id="conf_diatomic",
        elements=["H", "Cl"],
        atomic_numbers=[1, 17],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.27)],
    )
    ref = ConformerInput(
        conformer_id="conf_water",
        elements=["O", "H", "H"],
        atomic_numbers=[8, 1, 1],
        coordinates=[(0.0, 0.0, 0.117), (0.0, 0.757, -0.469), (0.0, -0.757, -0.469)],
    )
    with pytest.raises(IncompatibleTopologyError):
        align_conformers_by_mcs(target, ref)


def test_mcs_timeout_raises_custom_error():
    """REQ-TOPOS-013.1: Verify that an exhausted MCS timeout ceiling raises MCSConvergenceTimeoutError."""
    c1 = ConformerInput(
        conformer_id="polycycle_1",
        elements=["C"] * 10,
        atomic_numbers=[6] * 10,
        coordinates=[
            (0.00, 0.00, 0.00),
            (1.26, 0.89, 0.00),
            (2.52, 0.00, 0.00),
            (3.78, 0.89, 0.00),
            (5.04, 0.00, 0.00),
            (6.30, 0.89, 0.00),
            (7.56, 0.00, 0.00),
            (8.82, 0.89, 0.00),
            (10.08, 0.00, 0.00),
            (11.34, 0.89, 0.00),
        ],
    )
    c2 = ConformerInput(
        conformer_id="polycycle_2",
        elements=["C"] * 10,
        atomic_numbers=[6] * 10,
        coordinates=[
            (0.00, 0.00, 0.00),
            (0.89, 1.26, 0.00),
            (0.00, 2.52, 0.00),
            (0.89, 3.78, 0.00),
            (0.00, 5.04, 0.00),
            (0.89, 6.30, 0.00),
            (0.00, 7.56, 0.00),
            (0.89, 8.82, 0.00),
            (0.00, 10.08, 0.00),
            (0.89, 11.34, 0.00),
        ],
    )
    tight_config = MCSAlignmentConfig(timeout_seconds=0.0001)
    with pytest.raises(MCSConvergenceTimeoutError):
        align_conformers_by_mcs(c1, c2, config=tight_config)


def test_cluster_ensemble_deduplication():
    """REQ-TOPOS-013.5: Verify pairwise RMSD calculation and duplicate cluster grouping."""
    ref = ConformerInput(
        conformer_id="ref_methane",
        elements=["C", "H", "H", "H", "H"],
        atomic_numbers=[6, 1, 1, 1, 1],
        coordinates=[
            (0.000, 0.000, 0.000),
            (0.629, 0.629, 0.629),
            (-0.629, -0.629, 0.629),
            (-0.629, 0.629, -0.629),
            (0.629, -0.629, -0.629),
        ],
    )
    dup = ConformerInput(
        conformer_id="dup_methane",
        elements=ref.elements,
        atomic_numbers=ref.atomic_numbers,
        coordinates=ref.coordinates,
    )
    summary = cluster_ensemble_conformers([ref, dup], reference=ref)
    assert summary.total_conformers == 2
    assert len(summary.duplicate_clusters) >= 1
    assert "dup_methane" in summary.duplicate_clusters[0] or "ref_methane" in summary.duplicate_clusters[0]


def test_persist_aligned_ensemble_h5_roundtrip(tmp_path, monkeypatch):
    """REQ-TOPOS-013.6: Verify thread-safe HDF5 persistence and air-gap boundary check."""
    store_dir = tmp_path / "topos_store"
    store_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCH_STORE_DIR", str(store_dir))

    summary = EnsembleAlignmentSummary(
        ensemble_id="test_ensemble_01",
        reference_id="ref_01",
        total_conformers=1,
        aligned_conformers=[
            AlignedConformerResult(
                conformer_id="conf_01",
                reference_id="ref_01",
                rmsd_angstrom=0.05,
                rotation_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                translation_vector=[0.0, 0.0, 0.0],
                aligned_coordinates=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                atom_mapping={0: 0, 1: 1, 2: 2},
                execution_duration_seconds=0.01,
            )
        ],
        pairwise_rmsd_matrix=[[0.0]],
        duplicate_clusters=[],
        mcs_mapping={0: 0, 1: 1, 2: 2},
        aligned_mcs_coords=[[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
    )

    archive_path = store_dir / "ensemble_01.h5"
    out_path = persist_aligned_ensemble_h5(summary, archive_path)
    assert out_path.exists()

    with h5py.File(out_path, "r") as h5f:
        assert f"/ensembles/{summary.ensemble_id}/aligned_coords" in h5f
        assert f"/ensembles/{summary.ensemble_id}/pairwise_rmsd" in h5f
        assert f"/ensembles/{summary.ensemble_id}/mcs_mapping" in h5f

    # Air-gap violation check
    outside_path = tmp_path / "unauthorized" / "leak.h5"
    with pytest.raises(AirGapBoundaryViolationError):
        persist_aligned_ensemble_h5(summary, outside_path)


def test_concurrency_tier_detection(monkeypatch):
    """REQ-TOPOS-013.6: Verify concurrency tier detection logic across environment markers."""
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    assert detect_concurrency_tier() == StorageTier.TIER6_HPC
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert detect_concurrency_tier() == StorageTier.TIER5_GITHUB_ACTIONS
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    monkeypatch.setenv("CODESPACES", "true")
    assert detect_concurrency_tier() == StorageTier.TIER4_CODESPACES
    monkeypatch.delenv("CODESPACES", raising=False)


def test_mass_weighted_alignment_preserves_so3_and_calculates_analytical_rmsd():
    """REQ-TOPOS-013.2 & REQ-TOPOS-013.4: Verify mass-weighted alignment dynamically pulls masses via mendeleev."""
    c1 = ConformerInput(
        conformer_id="water_1",
        elements=["O", "H", "H"],
        atomic_numbers=[8, 1, 1],
        coordinates=[(0.0, 0.0, 0.117), (0.0, 0.757, -0.469), (0.0, -0.757, -0.469)],
    )
    c2 = ConformerInput(
        conformer_id="water_2",
        elements=["O", "H", "H"],
        atomic_numbers=[8, 1, 1],
        coordinates=[(0.0, 0.0, 0.117), (0.0, 0.757, -0.469), (0.0, -0.757, -0.469)],
    )
    cfg = MCSAlignmentConfig(mass_weighting=True)
    res = align_conformers_by_mcs(c1, c2, config=cfg)
    assert res.rmsd_angstrom < 1e-4
    assert np.allclose(np.array(res.rotation_matrix).T @ np.array(res.rotation_matrix), np.eye(3), atol=1e-4)
    assert np.isclose(np.linalg.det(np.array(res.rotation_matrix)), 1.0, atol=1e-4)


def test_heterogeneous_ensemble_persistence_h5(tmp_path, monkeypatch):
    """REQ-TOPOS-013.6: Verify HDF5 persistence for heterogeneous ensembles with differing atom counts."""
    store_dir = tmp_path / "topos_store"
    store_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCH_STORE_DIR", str(store_dir))

    conf_3atom = AlignedConformerResult(
        conformer_id="conf_3",
        reference_id="ref_root",
        rmsd_angstrom=0.01,
        rotation_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        translation_vector=[0.0, 0.0, 0.0],
        aligned_coordinates=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        atom_mapping={0: 0, 1: 1, 2: 2},
        execution_duration_seconds=0.005,
    )
    conf_4atom = AlignedConformerResult(
        conformer_id="conf_4",
        reference_id="ref_root",
        rmsd_angstrom=0.02,
        rotation_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        translation_vector=[0.0, 0.0, 0.0],
        aligned_coordinates=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)],
        atom_mapping={0: 0, 1: 1, 2: 2},
        execution_duration_seconds=0.006,
    )
    summary = EnsembleAlignmentSummary(
        ensemble_id="ens_hetero_01",
        reference_id="ref_root",
        total_conformers=2,
        aligned_conformers=[conf_3atom, conf_4atom],
        pairwise_rmsd_matrix=[[0.0, 0.1], [0.1, 0.0]],
        duplicate_clusters=[],
        mcs_mapping={0: 0, 1: 1, 2: 2},
    )

    archive_path = store_dir / "hetero_ensemble.h5"
    out_path = persist_aligned_ensemble_h5(summary, archive_path)
    assert out_path.exists()

    with h5py.File(out_path, "r") as h5f:
        assert f"/ensembles/{summary.ensemble_id}/conformers/conf_3/aligned_coords" in h5f
        assert f"/ensembles/{summary.ensemble_id}/conformers/conf_4/aligned_coords" in h5f
        assert f"/ensembles/{summary.ensemble_id}/pairwise_rmsd" in h5f

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\tautomer.py ---
"""CoChem-TOPOS Chemical Perception Subsystem: Prototropic Tautomer Enumeration.

Pure in-memory BFS state traversal, directional SMIRKS transforms, Patterson scoring,
BSSE ghost-atom exclusion, dynamic Mendeleev atomic masses and covalent radii,
downstream semi-empirical thermodynamic filtering, and thread-safe HDF5 persistence [M][D][E].
"""

from __future__ import annotations

import collections
import concurrent.futures
import hashlib
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple, Union

import filelock
import h5py
from mendeleev import element
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from rdkit import Chem
from rdkit.Chem import AllChem, rdDistGeom

logger = logging.getLogger(__name__)

# Enforce JAX 64-bit precision invariant per Method Matrix
os.environ["JAX_ENABLE_X64"] = "True"

# Intra-process lock for HDF5 persistence (safeguards non-threadsafe h5py builds)
_HDF5_THREAD_LOCK = threading.Lock()


# ============================================================================
# DOMAIN EXCEPTION HIERARCHY
# ============================================================================


class ToposPerceptionError(Exception):
    """Base exception for chemical perception and tautomer failures [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TautomerEnumerationTimeoutError(ToposPerceptionError):
    """Raised when tautomer state space traversal exceeds execution timeout ceiling [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TautomerCombinatorialLimitExceededError(ToposPerceptionError):
    """Raised when generated tautomer states exceed configured bounds in 'raise' mode [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ValenceConservationError(ToposPerceptionError):
    """Raised when a prototropic transform violates octet or valency conservation [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class InvalidTopologyInputError(ToposPerceptionError):
    """Raised when input molecular structure is unparseable or topologically malformed [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TautomerCanonicalizationError(ToposPerceptionError):
    """Raised when canonical tautomer selection or fixed-H InChIKey hashing fails [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TautomerPersistenceError(ToposPerceptionError):
    """Raised when HDF5 serialization or deserialization fails [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TautomerStorageLockTimeoutError(ToposPerceptionError):
    """Raised when acquiring cross-platform filelock exceeds timeout ceiling [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class QuantumChemistryHandshakeError(ToposPerceptionError):
    """Raised when downstream 3D embedding or GFN2-xTB pre-filtering fails [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class GhostAtomSanitizationError(ToposPerceptionError):
    """Raised when BSSE ghost atoms cannot be harmonized with topology contracts [D]."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


# ============================================================================
# PYDANTIC V2 DOMAIN MODELS
# ============================================================================


class TopologyInput(BaseModel):
    """Immutable molecular topology record ingesting 2D/3D inputs with BSSE ghost handling [M][D]."""

    model_config = ConfigDict(frozen=True)

    molecule_id: str = Field(..., description="Unique alphanumeric identifier for the molecule")
    smiles: Optional[str] = Field(default=None, description="Input SMILES string")
    elements: List[str] = Field(..., min_length=1, description="Elemental symbols")
    atomic_numbers: List[int] = Field(..., min_length=1, description="IUPAC atomic numbers Z")
    coordinates: Optional[List[Tuple[float, float, float]]] = Field(
        default=None, description="Cartesian 3D coordinates in Angstroms (x, y, z)"
    )
    bonds: List[Tuple[int, int, float]] = Field(
        default_factory=list, description="Edges: (idx_i, idx_j, order)"
    )
    formal_charges: List[int] = Field(default_factory=list, description="Formal charge per atom")
    masses: Optional[List[float]] = Field(
        default=None, description="Atomic masses dynamically queried via mendeleev"
    )
    is_ghost: List[bool] = Field(
        default_factory=list, description="Mask identifying BSSE ghost atoms"
    )

    @model_validator(mode="before")
    @classmethod
    def pre_validate_arrays_and_defaults(cls, data: Any) -> Any:
        """Pre-validation hook to align default masks, formal charges, and dynamic masses [M][D]."""
        if not isinstance(data, dict):
            return data

        elements_list = data.get("elements", [])
        n_atoms = len(elements_list)
        atomic_numbers = data.get("atomic_numbers", [])

        # Auto-detect ghost atoms: Z=0 or symbol in {"GH", "BQ", "X"}
        if "is_ghost" not in data or not data["is_ghost"]:
            ghost_symbols = {"GH", "BQ", "X"}
            data["is_ghost"] = [
                (z == 0 or sym.upper() in ghost_symbols)
                for z, sym in zip(atomic_numbers, elements_list)
            ] if len(atomic_numbers) == n_atoms else [False] * n_atoms

        if "formal_charges" not in data or not data["formal_charges"]:
            data["formal_charges"] = [0] * n_atoms

        # Dynamic Mendeleev mass retrieval mandate: non-ghosts queried, ghosts get 0.0 without call
        if "masses" not in data or data.get("masses") is None:
            if len(atomic_numbers) == n_atoms:
                computed_masses: List[float] = []
                for z, ghost in zip(atomic_numbers, data["is_ghost"]):
                    if ghost or z == 0:
                        computed_masses.append(0.0)
                    else:
                        elem_obj = element(int(z))
                        computed_masses.append(float(elem_obj.mass))
                data["masses"] = computed_masses

        return data

    @model_validator(mode="after")
    def validate_integrity(self) -> "TopologyInput":
        """Post-validation enforcing coordinate integrity, array lengths, and bond bounds [M]."""
        n_atoms = len(self.elements)
        if not self.smiles and not self.coordinates and not self.bonds:
            raise ValueError("At least one of smiles, coordinates, or explicit bonds must be provided")

        if self.coordinates is not None and len(self.coordinates) != n_atoms:
            raise ValueError(f"coordinates length {len(self.coordinates)} != elements length {n_atoms}")

        if len(self.atomic_numbers) != n_atoms:
            raise ValueError(f"atomic_numbers length {len(self.atomic_numbers)} != elements length {n_atoms}")

        if len(self.is_ghost) != n_atoms:
            raise ValueError(f"is_ghost length {len(self.is_ghost)} != elements length {n_atoms}")

        if len(self.formal_charges) != n_atoms:
            raise ValueError(f"formal_charges length {len(self.formal_charges)} != elements length {n_atoms}")

        if self.masses is not None and len(self.masses) != n_atoms:
            raise ValueError(f"masses length {len(self.masses)} != elements length {n_atoms}")

        for idx_i, idx_j, order in self.bonds:
            if not (0 <= idx_i < n_atoms and 0 <= idx_j < n_atoms):
                raise ValueError(f"Bond ({idx_i}, {idx_j}) references out-of-bounds atom index for n_atoms={n_atoms}")
            if idx_i == idx_j:
                raise ValueError(f"Self-referential bond ({idx_i}, {idx_j}) detected")
            if order <= 0.0 or order > 4.0:
                raise ValueError(f"Invalid bond order {order} for bond ({idx_i}, {idx_j})")

        return self


class TautomerCandidate(BaseModel):
    """Immutable record representing an enumerated tautomeric state [M][D]."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., description="Unique candidate hash")
    smiles: str = Field(..., min_length=1, description="Canonical SMILES of the tautomer")
    inchi_key: str = Field(..., min_length=27, max_length=27, description="Standard InChIKey (27 chars)")
    fixed_h_inchi_key: str = Field(..., min_length=27, max_length=27, description="Fixed-H InChIKey (27 chars)")
    canonical_score: float = Field(..., description="Patterson score (higher is more favorable)")
    relative_energy_kcal_mol: Optional[float] = Field(
        default=None, description="Relative electronic energy from xTB"
    )
    is_canonical: bool = Field(default=False, description="Flag indicating highest-ranking canonical tautomer")
    transform_depth: int = Field(..., ge=0, description="Number of elementary prototropic shifts from parent")
    transform_history: List[str] = Field(default_factory=list, description="Sequence of SMIRKS applied")


class TautomerEnumerationConfig(BaseModel):
    """Configuration parameters and combinatorial ceilings for tautomer exploration [M][D]."""

    model_config = ConfigDict(frozen=True)

    max_tautomers: int = Field(default=500, ge=1, le=10000, description="Max unique tautomers before truncation")
    max_transform_depth: int = Field(default=6, ge=1, le=20, description="Max search depth from parent topology")
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0, description="Process-level timeout limit in seconds")
    energy_cutoff_kcal_mol: float = Field(default=15.0, ge=0.0, description="Thermodynamic exclusion ceiling")
    truncation_policy: Literal["raise", "truncate"] = Field(
        default="truncate",
        description="Behavior when max_tautomers limit is reached"
    )


class TautomerEnsemble(BaseModel):
    """Validated ensemble of enumerated tautomer candidates for a parent molecule [M][D]."""

    model_config = ConfigDict(frozen=True)

    parent_id: str = Field(..., description="Parent molecule identifier")
    canonical_tautomer_id: str = Field(..., description="ID of designated canonical tautomer")
    total_generated: int = Field(..., ge=1, description="Total unique tautomers identified")
    candidates: List[TautomerCandidate] = Field(..., min_length=1, description="List of generated tautomer candidates")
    execution_duration_seconds: float = Field(..., ge=0.0, description="Wall-clock runtime for enumeration")

    @model_validator(mode="after")
    def validate_ensemble_consistency(self) -> "TautomerEnsemble":
        """Ensures ensemble internal consistency: counts, canonical pointer, and uniqueness [M]."""
        if len(self.candidates) != self.total_generated:
            raise ValueError(f"Candidate count {len(self.candidates)} != total_generated {self.total_generated}")

        candidate_map = {c.candidate_id: c for c in self.candidates}
        if self.canonical_tautomer_id not in candidate_map:
            raise ValueError(f"canonical_tautomer_id '{self.canonical_tautomer_id}' not found in candidates")

        canonical_count = sum(1 for c in self.candidates if c.is_canonical)
        if canonical_count != 1:
            raise ValueError(f"Exactly one candidate must have is_canonical=True; found {canonical_count}")

        if not candidate_map[self.canonical_tautomer_id].is_canonical:
            raise ValueError("Candidate matching canonical_tautomer_id must have is_canonical=True")

        return self


# ============================================================================
# DIRECTIONAL SMIRKS TRANSFORM LIBRARY
# ============================================================================

PROTOTROPIC_SMIRKS: Dict[str, str] = {
    # 1,3-Prototropic Shifts
    "keto_enol_fwd": "[O,S,Se,Te:1]=[#6:2]-[#6:3]-[#1:4]>>[#1:4]-[O,S,Se,Te:1]-[#6:2]=[#6:3]",
    "keto_enol_rev": "[#1:4]-[O,S,Se,Te:1]-[#6:2]=[#6:3]>>[O,S,Se,Te:1]=[#6:2]-[#6:3]-[#1:4]",
    "lactam_lactim_fwd": "[O,S:1]=[#6:2]-[#7:3]-[#1:4]>>[#1:4]-[O,S:1]-[#6:2]=[#7:3]",
    "lactam_lactim_rev": "[#1:4]-[O,S:1]-[#6:2]=[#7:3]>>[O,S:1]=[#6:2]-[#7:3]-[#1:4]",
    "heteroaromatic_lactam_lactim_fwd": "[O,S:1]=[c,C:2]:[n:3]-[#1:4]>>[#1:4]-[O,S:1]-[c:2]:[n:3]",
    "heteroaromatic_lactam_lactim_rev": "[#1:4]-[O,S:1]-[c,C:2]:[n:3]>>[O,S:1]=[c,C:2]:[n:3]-[#1:4]",
    "amidine_fwd": "[#7:1]=[#6:2]-[#7:3]-[#1:4]>>[#1:4]-[#7:1]-[#6:2]=[#7:3]",
    "amidine_rev": "[#1:4]-[#7:1]-[#6:2]=[#7:3]>>[#7:1]=[#6:2]-[#7:3]-[#1:4]",
    "imine_enamine_fwd": "[#7:1]=[#6:2]-[#6:3]-[#1:4]>>[#1:4]-[#7:1]-[#6:2]=[#6:3]",
    "imine_enamine_rev": "[#1:4]-[#7:1]-[#6:2]=[#6:3]>>[#7:1]=[#6:2]-[#6:3]-[#1:4]",
    "nitroso_oxime_fwd": "[O:1]=[#7:2]-[#6:3]-[#1:4]>>[#1:4]-[O:1]-[#7:2]=[#6:3]",
    "nitroso_oxime_rev": "[#1:4]-[O:1]-[#7:2]=[#6:3]>>[O:1]=[#7:2]-[#6:3]-[#1:4]",
    # 1,5-Prototropic Shifts (Conjugated & Vinylogous Systems)
    "vinylogous_keto_enol_fwd": "[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#6:5]-[#1:6]>>[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#6:5]",
    "vinylogous_keto_enol_rev": "[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#6:5]>>[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#6:5]-[#1:6]",
    "vinylogous_amide_fwd": "[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#7:5]-[#1:6]>>[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]=[#7:5]",
    "vinylogous_amide_rev": "[#1:6]-[O,S:1]-[#6:2]=[#6:3]-[#6:4]-[#7:5]>>[O,S:1]=[#6:2]-[#6:3]=[#6:4]-[#7:5]-[#1:6]",
    # Heterocyclic Annular Shifts
    "diaza_1_3": "[#1:6]-[n:1]1:[c,n:2]:[n:3]:[c,n:4]:[c,n:5]1>>[n:1]1:[c,n:2]:[n:3](-[#1:6]):[c,n:4]:[c,n:5]1",
    "diaza_1_2": "[#1:6]-[n:1]1:[n:2]:[c,n:3]:[c,n:4]:[c,n:5]1>>[n:1]1:[n:2](-[#1:6]):[c,n:3]:[c,n:4]:[c,n:5]1",
}


# ============================================================================
# CANONICAL PATTERSON SCORING
# ============================================================================


def compute_patterson_score(mol: Chem.Mol) -> float:
    """Computes heuristic Patterson canonical score for tautomer ranking [M][D].

    Scoring criteria:
    - +100 per fully aromatic ring
    - +50 per keto/carbonyl group over enol (non-phenolic context)
    - +25 per lactam over lactim group
    - -50 per aci-nitro group
    - -100 per isolated charge pair / zwitterionic separation
    """
    score = 0.0

    # 1. Fully aromatic rings (+100 each)
    ssr = Chem.GetSymmSSSR(mol)
    for ring_atom_indices in ssr:
        if all(mol.GetAtomWithIdx(idx).GetIsAromatic() for idx in ring_atom_indices):
            score += 100.0

    # 2. Keto / carbonyl group over enol (+50 each)
    # Carbonyl [#6;!$([#6](=O)[O,N,S,F,Cl,Br,I])](=O)
    keto_smarts = "[#6;!$([#6](=O)[O,N,S,F,Cl,Br,I])](=O)"
    keto_query = Chem.MolFromSmarts(keto_smarts)
    if keto_query is not None:
        score += 50.0 * len(mol.GetSubstructMatches(keto_query))

    # 3. Lactam over lactim group (+25 each)
    lactam_smarts = "[O,S]=[#6,c;R]-[n,N;R;!H0]"
    lactam_query = Chem.MolFromSmarts(lactam_smarts)
    if lactam_query is not None:
        score += 25.0 * len(mol.GetSubstructMatches(lactam_query))

    # 4. Aci-nitro group (-50 each)
    aci_smarts = "[#6]=[N+](-[O-])[O;H1]"
    aci_query = Chem.MolFromSmarts(aci_smarts)
    if aci_query is not None:
        score -= 50.0 * len(mol.GetSubstructMatches(aci_query))

    # 5. Isolated charge or zwitterionic separation (-100 per separated pair = -50 per charge)
    total_abs_charge = sum(abs(a.GetFormalCharge()) for a in mol.GetAtoms())
    score -= 50.0 * float(total_abs_charge)

    return score


# ============================================================================
# HELPER: GRAPH CONSTRUCTION AND SANITIZATION
# ============================================================================


def _build_rdkit_mol_from_topology(top: TopologyInput) -> Chem.Mol:
    """Builds an RDKit Mol object from TopologyInput, honoring dynamic covalent radii [M][D]."""
    if top.smiles:
        mol = Chem.MolFromSmiles(top.smiles)
        if mol is None:
            raise InvalidTopologyInputError(f"Failed to parse SMILES '{top.smiles}'")
        return mol

    n_atoms = len(top.elements)
    em = Chem.EditableMol(Chem.Mol())

    # Add atoms
    for i in range(n_atoms):
        z = top.atomic_numbers[i]
        ghost = top.is_ghost[i]
        atom = Chem.Atom(0 if (ghost or z == 0) else int(z))
        atom.SetFormalCharge(top.formal_charges[i])
        em.AddAtom(atom)

    if top.bonds:
        # Explicit bond connectivity
        for idx_i, idx_j, order in top.bonds:
            if order >= 3.5:
                btype = Chem.BondType.QUADRUPLE
            elif order >= 2.5:
                btype = Chem.BondType.TRIPLE
            elif order >= 1.75:
                btype = Chem.BondType.DOUBLE
            elif order >= 1.25:
                btype = Chem.BondType.AROMATIC
            else:
                btype = Chem.BondType.SINGLE
            em.AddBond(idx_i, idx_j, btype)
        mol = em.GetMol()
    elif top.coordinates is not None:
        # Reconstruct connectivity from 3D Cartesian coordinates using Pyykkö covalent radii
        coords_arr = np.asarray(top.coordinates, dtype=np.float64)
        covalent_radii: List[float] = []
        for i in range(n_atoms):
            if top.is_ghost[i] or top.atomic_numbers[i] == 0:
                covalent_radii.append(0.0)
            else:
                el = element(int(top.atomic_numbers[i]))
                cov_pm = el.covalent_radius_pyykko
                covalent_radii.append(float(cov_pm) / 100.0 if cov_pm is not None else 0.77)

        for i in range(n_atoms):
            if top.is_ghost[i] or top.atomic_numbers[i] == 0:
                continue
            for j in range(i + 1, n_atoms):
                if top.is_ghost[j] or top.atomic_numbers[j] == 0:
                    continue
                dist = float(np.linalg.norm(coords_arr[i] - coords_arr[j]))
                r0 = covalent_radii[i] + covalent_radii[j]
                if dist <= r0 + 0.40:
                    em.AddBond(i, j, Chem.BondType.SINGLE)
        mol = em.GetMol()
    else:
        raise InvalidTopologyInputError("TopologyInput lacks smiles, explicit bonds, and coordinates")

    try:
        Chem.SanitizeMol(mol)
    except Exception as exc:
        raise InvalidTopologyInputError(f"RDKit sanitization failed on constructed topology: {exc}") from exc

    return mol


# ============================================================================
# WORKER PROCESS INITIALIZER AND BFS EXPLORATION ENGINE
# ============================================================================


def _cpu_worker_init() -> None:
    """Worker initializer enforcing strict CPU-bound execution and zero GPU context allocation [M]."""
    os.environ["CUDA_VISIBLE_DEVICES"] = ""


def _bfs_tautomer_worker(
    input_topology: TopologyInput,
    config: TautomerEnumerationConfig,
) -> TautomerEnsemble:
    """Internal algorithmic BFS worker executing bounded prototropic state traversal [M][D]."""
    start_time = time.perf_counter()

    root_mol = _build_rdkit_mol_from_topology(input_topology)

    # Check for all-ghost empty topology
    cleaned_root = Chem.DeleteSubstructs(root_mol, Chem.MolFromSmarts("[#0]"))
    if cleaned_root.GetNumAtoms() == 0:
        raise GhostAtomSanitizationError("Sanitization resulted in an empty molecular graph (only ghost atoms present)")

    # Prepare reaction objects
    rxn_objects: List[Tuple[str, AllChem.ChemicalReaction]] = [
        (name, AllChem.ReactionFromSmarts(smirks))
        for name, smirks in PROTOTROPIC_SMIRKS.items()
    ]

    # Convert root to explicit Hs for prototropic migration
    root_mol_hs = Chem.AddHs(root_mol)
    net_charge = sum(a.GetFormalCharge() for a in root_mol_hs.GetAtoms())
    total_hydrogens = sum(1 for a in root_mol_hs.GetAtoms() if a.GetAtomicNum() == 1)

    # State tracking: keyed by fixed-H InChIKey (the definitive deduplication key)
    visited_candidates: Dict[str, TautomerCandidate] = {}
    visited_depths: Dict[str, int] = {}

    def _register_candidate(mol: Chem.Mol, depth: int, history: List[str]) -> Optional[str]:
        """Processes and registers a molecular candidate. Returns fixed_h_inchi_key."""
        # Purge dummy/ghost atoms prior to computing InChI/InChIKeys
        cleaned_mol = Chem.DeleteSubstructs(mol, Chem.MolFromSmarts("[#0]"))
        if cleaned_mol.GetNumAtoms() == 0:
            return None

        # Remove explicit Hs for canonical SMILES generation
        mol_no_hs = Chem.RemoveHs(cleaned_mol)
        c_smiles = Chem.MolToSmiles(mol_no_hs)
        c_inchi_key = Chem.MolToInchiKey(cleaned_mol)
        c_fixed_h = Chem.MolToInchiKey(cleaned_mol, options="-FixedH")

        if not c_inchi_key or not c_fixed_h or len(c_inchi_key) != 27 or len(c_fixed_h) != 27:
            raise TautomerCanonicalizationError(
                f"Failed to generate valid 27-character InChIKeys for candidate '{c_smiles}'"
            )

        if c_fixed_h in visited_candidates:
            # Retain minimal transform depth
            if depth < visited_candidates[c_fixed_h].transform_depth:
                existing = visited_candidates[c_fixed_h]
                visited_candidates[c_fixed_h] = existing.model_copy(
                    update={"transform_depth": depth, "transform_history": history}
                )
            return c_fixed_h

        # New candidate: check combinatorial bound
        if len(visited_candidates) >= config.max_tautomers:
            if config.truncation_policy == "raise":
                raise TautomerCombinatorialLimitExceededError(
                    f"Generated tautomer count exceeded combinatorial limit of {config.max_tautomers}"
                )
            return None

        score = compute_patterson_score(mol_no_hs)
        cand_id = f"cand_{hashlib.sha256(f'{input_topology.molecule_id}_{c_fixed_h}'.encode('utf-8')).hexdigest()[:16]}"

        cand = TautomerCandidate(
            candidate_id=cand_id,
            smiles=c_smiles,
            inchi_key=c_inchi_key,
            fixed_h_inchi_key=c_fixed_h,
            canonical_score=score,
            relative_energy_kcal_mol=None,
            is_canonical=False,
            transform_depth=depth,
            transform_history=history,
        )
        visited_candidates[c_fixed_h] = cand
        visited_depths[c_fixed_h] = depth
        return c_fixed_h

    # Register root state
    root_fixed_h = _register_candidate(root_mol_hs, depth=0, history=[])
    if root_fixed_h is None:
        raise ToposPerceptionError("Failed to perceive and register parent root tautomer")

    # Queue holds: (mol_hs, depth, history)
    queue: collections.deque[Tuple[Chem.Mol, int, List[str]]] = collections.deque()
    queue.append((root_mol_hs, 0, []))

    # BFS Traversal loop
    while queue:
        # Check timeout ceiling
        if (time.perf_counter() - start_time) > config.timeout_seconds:
            raise TautomerEnumerationTimeoutError(
                f"Tautomer state space exploration exceeded timeout ceiling of {config.timeout_seconds}s"
            )

        current_mol, current_depth, current_history = queue.popleft()

        if current_depth >= config.max_transform_depth:
            continue

        for rule_name, rxn in rxn_objects:
            # Check timeout inside loop
            if (time.perf_counter() - start_time) > config.timeout_seconds:
                raise TautomerEnumerationTimeoutError(
                    f"Tautomer state space exploration exceeded timeout ceiling of {config.timeout_seconds}s"
                )

            try:
                products_list = rxn.RunReactants((current_mol,))
            except Exception:
                continue

            for prod_tuple in products_list:
                prod_mol = prod_tuple[0]

                # Sanitize and assign stereochemistry
                try:
                    Chem.SanitizeMol(prod_mol)
                    Chem.AssignStereochemistry(prod_mol, cleanIt=True, force=True)
                except Chem.AtomValenceException as val_err:
                    raise ValenceConservationError(f"Valence violation during transform '{rule_name}': {val_err}") from val_err
                except Exception:
                    continue

                # Conservation safeguards: net charge and total hydrogens (explicit nodes + implicit)
                q_prod = sum(a.GetFormalCharge() for a in prod_mol.GetAtoms())
                h_explicit = sum(1 for a in prod_mol.GetAtoms() if a.GetAtomicNum() == 1)
                h_implicit = sum(a.GetNumImplicitHs() for a in prod_mol.GetAtoms())
                total_h_prod = h_explicit + h_implicit
                if q_prod != net_charge:
                    raise ValenceConservationError(
                        f"Net formal charge violation: {q_prod} != parent {net_charge} under '{rule_name}'"
                    )
                if h_implicit > 0 or total_h_prod != total_hydrogens:
                    raise ValenceConservationError(
                        f"Hydrogen conservation violation: {h_explicit} explicit + {h_implicit} implicit != parent {total_hydrogens} under '{rule_name}'"
                    )

                next_depth = current_depth + 1
                next_history = current_history + [rule_name]

                # Clean ghost atoms for fixed_h lookup
                cleaned_prod = Chem.DeleteSubstructs(prod_mol, Chem.MolFromSmarts("[#0]"))
                prod_fixed_h = Chem.MolToInchiKey(cleaned_prod, options="-FixedH")

                if prod_fixed_h not in visited_candidates:
                    registered_key = _register_candidate(prod_mol, next_depth, next_history)
                    if registered_key is not None:
                        queue.append((prod_mol, next_depth, next_history))
                    elif config.truncation_policy == "truncate" and len(visited_candidates) >= config.max_tautomers:
                        # Graceful halt when combinatorial limit reached
                        queue.clear()
                        break
                else:
                    if next_depth < visited_depths.get(prod_fixed_h, 999):
                        visited_depths[prod_fixed_h] = next_depth
                        _register_candidate(prod_mol, next_depth, next_history)

    # Designate canonical tautomer: highest Patterson score, tie-break by lexicographically smallest SMILES
    candidates_list = list(visited_candidates.values())
    if not candidates_list:
        raise ToposPerceptionError("Tautomer exploration generated zero valid candidate states")

    # Sort: descending by canonical_score, ascending by canonical smiles
    candidates_list.sort(key=lambda c: (-c.canonical_score, c.smiles))

    canonical_id = candidates_list[0].candidate_id

    # Rebuild candidate list flagging exactly the single canonical winner
    final_candidates: List[TautomerCandidate] = []
    for c in candidates_list:
        is_can = (c.candidate_id == canonical_id)
        final_candidates.append(c.model_copy(update={"is_canonical": is_can}))

    elapsed = round(time.perf_counter() - start_time, 4)

    return TautomerEnsemble(
        parent_id=input_topology.molecule_id,
        canonical_tautomer_id=canonical_id,
        total_generated=len(final_candidates),
        candidates=final_candidates,
        execution_duration_seconds=elapsed,
    )


# ============================================================================
# PUBLIC API: ENUMERATION, FILTERING, PERSISTENCE
# ============================================================================


def enumerate_tautomers(
    input_topology: TopologyInput,
    config: TautomerEnumerationConfig,
) -> TautomerEnsemble:
    """Pure in-memory Tier 2 prototropic graph enumeration kernel [M][D].

    Executes bounded Breadth-First Search inside an isolated subprocess worker,
    adhering to CPU-only boundaries, process timeouts, and fixed-H InChIKey deduplication.
    """
    executor = concurrent.futures.ProcessPoolExecutor(max_workers=1, initializer=_cpu_worker_init)
    try:
        future = executor.submit(_bfs_tautomer_worker, input_topology, config)
        return future.result(timeout=config.timeout_seconds)
    except (concurrent.futures.TimeoutError, TimeoutError) as exc:
        for p in list(executor._processes.values()):
            try:
                p.terminate()
            except Exception as term_exc:
                logger.debug("Process termination handled: %s", term_exc)
        raise TautomerEnumerationTimeoutError(
            f"Tautomer enumeration exceeded timeout ceiling of {config.timeout_seconds} seconds"
        ) from exc
    except ToposPerceptionError:
        raise
    except Exception as exc:
        # Forward domain exceptions if raised in child process
        exc_str = str(exc)
        if "TautomerCombinatorialLimitExceededError" in exc_str:
            raise TautomerCombinatorialLimitExceededError(exc_str) from exc
        if "TautomerEnumerationTimeoutError" in exc_str:
            raise TautomerEnumerationTimeoutError(exc_str) from exc
        if "ValenceConservationError" in exc_str:
            raise ValenceConservationError(exc_str) from exc
        if "InvalidTopologyInputError" in exc_str:
            raise InvalidTopologyInputError(exc_str) from exc
        if "GhostAtomSanitizationError" in exc_str:
            raise GhostAtomSanitizationError(exc_str) from exc
        raise ToposPerceptionError(f"Tautomer enumeration failed: {exc}") from exc
    finally:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception as shut_exc:
            logger.debug("Executor shutdown handled: %s", shut_exc)


def filter_tautomers_thermodynamics(
    ensemble: TautomerEnsemble,
    config: TautomerEnumerationConfig,
    scratch_dir: Path,
) -> TautomerEnsemble:
    """Downstream adapter: generates 3D ETKDGv3 conformers and filters via GFN2-xTB / MMFF94 [M][D].

    Computes relative electronic energies Delta E_elec relative to the canonical tautomer,
    pruning candidates exceeding config.energy_cutoff_kcal_mol.
    """
    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    xtb_bin = shutil.which("xtb")
    raw_energies: Dict[str, float] = {}

    for cand in ensemble.candidates:
        mol = Chem.MolFromSmiles(cand.smiles)
        if mol is None:
            continue
        mol_h = Chem.AddHs(mol)

        # 3D Conformer generation via ETKDGv3
        params = rdDistGeom.ETKDGv3()
        params.randomSeed = 42
        cid = rdDistGeom.EmbedMolecule(mol_h, params)
        if cid < 0:
            cid = rdDistGeom.EmbedMolecule(mol_h, useRandomCoords=True)
            if cid < 0:
                continue

        # Energy evaluation: try xTB if available, else physical MMFF94 / UFF fallback
        energy_computed: Optional[float] = None

        if xtb_bin is not None:
            cand_scratch = scratch_dir / f"xtb_{cand.candidate_id}"
            cand_scratch.mkdir(parents=True, exist_ok=True)
            xyz_file = cand_scratch / "coord.xyz"
            Chem.MolToXYZFile(mol_h, str(xyz_file))
            try:
                res = subprocess.run(
                    [xtb_bin, "coord.xyz", "--sp"],
                    cwd=cand_scratch,
                    capture_output=True,
                    text=True,
                    timeout=30.0,
                )
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if "TOTAL ENERGY" in line:
                            # Parse Hartree and convert to kcal/mol (1 Hartree = 627.5095 kcal/mol)
                            hartree = float(line.split()[3])
                            energy_computed = hartree * 627.5095
                            break
            except Exception as xtb_exc:
                logger.warning("xTB execution failed for %s: %s; falling back to MMFF94", cand.candidate_id, xtb_exc)

        if energy_computed is None:
            # Physical MMFF94 / UFF force field evaluation
            try:
                mp = AllChem.MMFFGetMoleculeProperties(mol_h, mmffVariant="MMFF94")
                if mp is not None:
                    ff = AllChem.MMFFGetMoleculeForceField(mol_h, mp)
                    ff.Initialize()
                    ff.Minimize(maxIts=500)
                    energy_computed = float(ff.CalcEnergy())
                else:
                    ff = AllChem.UFFGetMoleculeForceField(mol_h)
                    ff.Initialize()
                    ff.Minimize(maxIts=500)
                    energy_computed = float(ff.CalcEnergy())
            except Exception as ff_exc:
                logger.warning("Force field evaluation failed for %s: %s", cand.candidate_id, ff_exc)

        if energy_computed is not None:
            raw_energies[cand.candidate_id] = energy_computed

    # Reference energy: canonical tautomer energy if available, else min energy
    canon_id = ensemble.canonical_tautomer_id
    ref_energy = raw_energies.get(canon_id, min(raw_energies.values()) if raw_energies else 0.0)

    # Filter candidates: retain canonical unconditionally; prune any exceeding energy cutoff
    filtered_candidates: List[TautomerCandidate] = []
    for cand in ensemble.candidates:
        if cand.candidate_id in raw_energies:
            delta_e = raw_energies[cand.candidate_id] - ref_energy
            if cand.is_canonical or delta_e <= (config.energy_cutoff_kcal_mol + 1e-4):
                filtered_candidates.append(
                    cand.model_copy(update={"relative_energy_kcal_mol": round(delta_e, 4)})
                )
        elif cand.is_canonical:
            # Always retain canonical tautomer
            filtered_candidates.append(cand)

    if not filtered_candidates:
        filtered_candidates = [
            c for c in ensemble.candidates if c.is_canonical
        ]

    return TautomerEnsemble(
        parent_id=ensemble.parent_id,
        canonical_tautomer_id=ensemble.canonical_tautomer_id,
        total_generated=len(filtered_candidates),
        candidates=filtered_candidates,
        execution_duration_seconds=ensemble.execution_duration_seconds,
    )


def save_tautomer_ensemble_to_hdf5(
    ensemble: TautomerEnsemble,
    hdf5_path: Path,
    lock_timeout: float = 30.0,
) -> Path:
    """Tier 3 persistence: serializes tautomer candidates and metadata into HDF5 archive [M][D].

    Uses fixed-width UTF-8 strings (S256 for SMILES, S32 for InChIKeys), chunking,
    GZIP level 4 compression, and filelock synchronization.
    """
    hdf5_path = Path(hdf5_path)
    lock_path = hdf5_path.with_suffix(".h5.lock")
    flock = filelock.FileLock(str(lock_path), timeout=lock_timeout)

    try:
        with _HDF5_THREAD_LOCK:
            try:
                with flock.acquire(timeout=lock_timeout):
                    hdf5_path.parent.mkdir(parents=True, exist_ok=True)
                    with h5py.File(hdf5_path, "a") as f:
                        grp_name = f"/tautomers/{ensemble.parent_id}"
                        if grp_name in f:
                            del f[grp_name]
                        grp = f.create_group(grp_name)

                        # Group metadata
                        grp.attrs["parent_id"] = str(ensemble.parent_id)
                        grp.attrs["canonical_tautomer_id"] = str(ensemble.canonical_tautomer_id)
                        grp.attrs["total_generated"] = int(ensemble.total_generated)
                        grp.attrs["execution_duration_seconds"] = float(ensemble.execution_duration_seconds)

                        n = len(ensemble.candidates)
                        chunks = (min(n, 128),) if n > 0 else None

                        # Explicit fixed-width datatypes
                        s256_dt = h5py.string_dtype(encoding="utf-8", length=256)
                        s32_dt = h5py.string_dtype(encoding="utf-8", length=32)
                        s64_dt = h5py.string_dtype(encoding="utf-8", length=64)

                        cand_ids = np.array([c.candidate_id for c in ensemble.candidates], dtype=s64_dt)
                        smiles_arr = np.array([c.smiles for c in ensemble.candidates], dtype=s256_dt)
                        ik_arr = np.array([c.inchi_key for c in ensemble.candidates], dtype=s32_dt)
                        fik_arr = np.array([c.fixed_h_inchi_key for c in ensemble.candidates], dtype=s32_dt)
                        scores_arr = np.array([c.canonical_score for c in ensemble.candidates], dtype=np.float64)
                        rel_e_arr = np.array(
                            [
                                c.relative_energy_kcal_mol if c.relative_energy_kcal_mol is not None else np.nan
                                for c in ensemble.candidates
                            ],
                            dtype=np.float64,
                        )
                        is_canon_arr = np.array([c.is_canonical for c in ensemble.candidates], dtype=np.bool_)
                        depths_arr = np.array([c.transform_depth for c in ensemble.candidates], dtype=np.int32)

                        grp.create_dataset("candidate_id", data=cand_ids, dtype=s64_dt, chunks=chunks, compression="gzip", compression_opts=4)
                        grp.create_dataset("smiles", data=smiles_arr, dtype=s256_dt, chunks=chunks, compression="gzip", compression_opts=4)
                        grp.create_dataset("inchi_key", data=ik_arr, dtype=s32_dt, chunks=chunks, compression="gzip", compression_opts=4)
                        grp.create_dataset("fixed_h_inchi_key", data=fik_arr, dtype=s32_dt, chunks=chunks, compression="gzip", compression_opts=4)
                        grp.create_dataset("canonical_score", data=scores_arr, dtype=np.float64, chunks=chunks, compression="gzip", compression_opts=4)
                        grp.create_dataset("relative_energy_kcal_mol", data=rel_e_arr, dtype=np.float64, chunks=chunks, compression="gzip", compression_opts=4)
                        grp.create_dataset("is_canonical", data=is_canon_arr, dtype=np.bool_, chunks=chunks, compression="gzip", compression_opts=4)
                        grp.create_dataset("transform_depth", data=depths_arr, dtype=np.int32, chunks=chunks, compression="gzip", compression_opts=4)

                    return hdf5_path
            except filelock.Timeout as exc:
                raise TautomerStorageLockTimeoutError(
                    f"Timed out acquiring storage filelock on '{lock_path}' after {lock_timeout}s"
                ) from exc
    except ToposPerceptionError:
        raise
    except Exception as exc:
        raise TautomerPersistenceError(f"Failed to persist tautomer ensemble to '{hdf5_path}': {exc}") from exc


def load_tautomer_ensemble_from_hdf5(
    hdf5_path: Path,
    molecule_id: str,
    lock_timeout: float = 30.0,
) -> TautomerEnsemble:
    """Tier 3 persistence: retrieves and reconstructs validated TautomerEnsemble from HDF5 archive [M][D]."""
    hdf5_path = Path(hdf5_path)
    if not hdf5_path.exists():
        raise TautomerPersistenceError(f"Target HDF5 archive does not exist: '{hdf5_path}'")

    lock_path = hdf5_path.with_suffix(".h5.lock")
    flock = filelock.FileLock(str(lock_path), timeout=lock_timeout)

    try:
        with _HDF5_THREAD_LOCK:
            try:
                with flock.acquire(timeout=lock_timeout):
                    with h5py.File(hdf5_path, "r") as f:
                        grp_path = f"/tautomers/{molecule_id}"
                        if grp_path not in f:
                            raise TautomerPersistenceError(
                                f"Molecule ID '{molecule_id}' not found under '/tautomers/' in '{hdf5_path}'"
                            )
                        grp = f[grp_path]

                        parent_id = str(grp.attrs["parent_id"])
                        canonical_tautomer_id = str(grp.attrs["canonical_tautomer_id"])
                        total_generated = int(grp.attrs["total_generated"])
                        exec_duration = float(grp.attrs["execution_duration_seconds"])

                        cand_ids = grp["candidate_id"][:]
                        smiles_arr = grp["smiles"][:]
                        ik_arr = grp["inchi_key"][:]
                        fik_arr = grp["fixed_h_inchi_key"][:]
                        scores_arr = grp["canonical_score"][:]
                        rel_e_arr = grp["relative_energy_kcal_mol"][:]
                        is_canon_arr = grp["is_canonical"][:]
                        depths_arr = grp["transform_depth"][:]

                        candidates: List[TautomerCandidate] = []
                        for i in range(len(cand_ids)):
                            cid = cand_ids[i].decode("utf-8") if isinstance(cand_ids[i], bytes) else str(cand_ids[i])
                            smi = smiles_arr[i].decode("utf-8") if isinstance(smiles_arr[i], bytes) else str(smiles_arr[i])
                            ik = ik_arr[i].decode("utf-8") if isinstance(ik_arr[i], bytes) else str(ik_arr[i])
                            fik = fik_arr[i].decode("utf-8") if isinstance(fik_arr[i], bytes) else str(fik_arr[i])
                            sc = float(scores_arr[i])
                            re = float(rel_e_arr[i])
                            rel_e = None if np.isnan(re) else re
                            is_c = bool(is_canon_arr[i])
                            dep = int(depths_arr[i])

                            candidates.append(
                                TautomerCandidate(
                                    candidate_id=cid,
                                    smiles=smi,
                                    inchi_key=ik,
                                    fixed_h_inchi_key=fik,
                                    canonical_score=sc,
                                    relative_energy_kcal_mol=rel_e,
                                    is_canonical=is_c,
                                    transform_depth=dep,
                                    transform_history=[],
                                )
                            )

                        return TautomerEnsemble(
                            parent_id=parent_id,
                            canonical_tautomer_id=canonical_tautomer_id,
                            total_generated=total_generated,
                            candidates=candidates,
                            execution_duration_seconds=exec_duration,
                        )
            except filelock.Timeout as exc:
                raise TautomerStorageLockTimeoutError(
                    f"Timed out acquiring storage filelock on '{lock_path}' after {lock_timeout}s"
                ) from exc
    except ToposPerceptionError:
        raise
    except Exception as exc:
        raise TautomerPersistenceError(f"Failed to load tautomer ensemble from '{hdf5_path}': {exc}") from exc

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_topos_tautomer.py ---
"""Physical Verification Test Suite for CoChem-TOPOS Chemical Perception Part 1.

Verifies 1,3- and 1,5-prototropic shifts, heterocyclic annular shifts, BFS state space bounds,
fixed-H InChIKey deduplication, Patterson scoring, BSSE ghost-atom exclusion, dynamic Mendeleev masses,
thermodynamic filtering, and thread-safe HDF5 persistence [M][D][E].
"""

from __future__ import annotations

import os
from pathlib import Path
import time
import filelock
import h5py
from mendeleev import element
import numpy as np
from pydantic import ValidationError
import pytest
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

from cochem.topos.tautomer import (
    GhostAtomSanitizationError,
    InvalidTopologyInputError,
    QuantumChemistryHandshakeError,
    TautomerCandidate,
    TautomerCanonicalizationError,
    TautomerCombinatorialLimitExceededError,
    TautomerEnsemble,
    TautomerEnumerationConfig,
    TautomerEnumerationTimeoutError,
    TautomerPersistenceError,
    TautomerStorageLockTimeoutError,
    TopologyInput,
    ToposPerceptionError,
    ValenceConservationError,
    compute_patterson_score,
    enumerate_tautomers,
    filter_tautomers_thermodynamics,
    load_tautomer_ensemble_from_hdf5,
    save_tautomer_ensemble_to_hdf5,
)


def test_1_3_prototropic_shifts():
    """REQ-TOPOS-014.1a: Verify 1,3-prototropic shifts across keto-enol, lactam-lactim, and amidine systems.

    Ensures net formal charge and total hydrogen count are strictly conserved [M][D].
    """
    # 1. Acetylacetone (keto-enol)
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens_acac = enumerate_tautomers(acac, config)
    assert ens_acac.total_generated >= 2
    smiles_pool = {c.smiles for c in ens_acac.candidates}
    # Enol form must be generated
    assert any("O" in s and "=" in s for s in smiles_pool)

    # 2. 2-Pyridone (heteroaromatic lactam-lactim)
    pyridone = TopologyInput(
        molecule_id="2_pyridone",
        smiles="c1cc[nH]c(=O)c1",
        elements=["C", "C", "C", "N", "C", "O", "C"],
        atomic_numbers=[6, 6, 6, 7, 6, 8, 6],
    )
    ens_pyr = enumerate_tautomers(pyridone, config)
    assert ens_pyr.total_generated >= 2
    pyr_smiles = {c.smiles for c in ens_pyr.candidates}
    assert any("Oc1ccccn1" in s or "c1ccncc1O" in s or "n" in s for s in pyr_smiles)

    # 3. Acetamidine (amidine-amidine)
    acetamidine = TopologyInput(
        molecule_id="acetamidine",
        smiles="CC(=N)N",
        elements=["C", "C", "N", "N"],
        atomic_numbers=[6, 6, 7, 7],
    )
    ens_amd = enumerate_tautomers(acetamidine, config)
    assert ens_amd.total_generated >= 1
    for c in ens_amd.candidates:
        assert c.fixed_h_inchi_key is not None
        assert len(c.fixed_h_inchi_key) == 27


def test_1_5_prototropic_shifts():
    """REQ-TOPOS-014.1b: Verify 1,5-prototropic shifts across conjugated systems (glutaconic acid, vinylogous amide) [M][D]."""
    # 1. Glutaconic acid (conjugated diacid)
    glutaconic = TopologyInput(
        molecule_id="glutaconic_acid",
        smiles="OC(=O)CC=CC(=O)O",
        elements=["O", "C", "O", "C", "C", "C", "C", "O", "O"],
        atomic_numbers=[8, 6, 8, 6, 6, 6, 6, 8, 8],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens_glut = enumerate_tautomers(glutaconic, config)
    assert ens_glut.total_generated >= 2
    # Net formal charge, transform depth bounds, and strict chemical formula conservation (C5H6O4)
    for cand in ens_glut.candidates:
        assert cand.transform_depth <= config.max_transform_depth
        m = Chem.AddHs(Chem.MolFromSmiles(cand.smiles))
        assert rdMolDescriptors.CalcMolFormula(m) == "C5H6O4"
        assert sum(1 for a in m.GetAtoms() if a.GetAtomicNum() == 1) == 6

    # 2. 3-Aminoacrolein / vinylogous amide (NC=CC=O)
    amide = TopologyInput(
        molecule_id="vinylogous_amide",
        smiles="NC=CC=O",
        elements=["N", "C", "C", "C", "O"],
        atomic_numbers=[7, 6, 6, 6, 8],
    )
    ens_amide = enumerate_tautomers(amide, config)
    assert ens_amide.total_generated >= 2
    for cand in ens_amide.candidates:
        m = Chem.AddHs(Chem.MolFromSmiles(cand.smiles))
        assert rdMolDescriptors.CalcMolFormula(m) == "C3H5NO"
        assert sum(1 for a in m.GetAtoms() if a.GetAtomicNum() == 1) == 5


def test_diaza_annular_shifts():
    """REQ-TOPOS-014.1c: Verify 1,2- and 1,3-diaza annular prototropic shifts across azoles [M][D]."""
    # 1H-1,2,3-triazole (c1cn[nH]n1) undergoing annular shifts
    triazole = TopologyInput(
        molecule_id="1H_triazole",
        smiles="c1cn[nH]n1",
        elements=["C", "C", "N", "N", "N"],
        atomic_numbers=[6, 6, 7, 7, 7],
    )
    config = TautomerEnumerationConfig(max_tautomers=20, max_transform_depth=3)
    ens_triazole = enumerate_tautomers(triazole, config)
    assert ens_triazole.total_generated >= 2
    for c in ens_triazole.candidates:
        assert len(c.fixed_h_inchi_key) == 27


def test_bfs_traversal_combinatorial_limits_and_timeout():
    """REQ-TOPOS-014.2: Verify bounds on state space traversal, truncation policies, and process timeout [M][D]."""
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    # Test max_tautomers truncation policy 'truncate'
    config_trunc = TautomerEnumerationConfig(max_tautomers=1, truncation_policy="truncate")
    ens_trunc = enumerate_tautomers(acac, config_trunc)
    assert ens_trunc.total_generated <= 1

    # Test max_tautomers truncation policy 'raise'
    config_raise = TautomerEnumerationConfig(max_tautomers=1, truncation_policy="raise")
    with pytest.raises(TautomerCombinatorialLimitExceededError):
        enumerate_tautomers(acac, config_raise)

    # Test timeout ceiling (using sub-second timeout enabled by gt=0.0)
    config_timeout = TautomerEnumerationConfig(timeout_seconds=0.0001)
    with pytest.raises(TautomerEnumerationTimeoutError):
        enumerate_tautomers(acac, config_timeout)


def test_deduplication_fixed_h_inchikey_and_canonicalization():
    """REQ-TOPOS-014.3: Verify deduplication via Fixed-H InChIKeys and Patterson scoring canonicalization.

    4-Methyl-1H-imidazole tautomers share standard InChIKey but diverge on fixed-H InChIKey [M][D].
    """
    med = TopologyInput(
        molecule_id="4_methyl_imidazole",
        smiles="Cc1c[nH]cn1",
        elements=["C", "C", "C", "N", "C", "N"],
        atomic_numbers=[6, 6, 6, 7, 6, 7],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens = enumerate_tautomers(med, config)
    assert ens.total_generated >= 2

    # Standard InChIKeys match, Fixed-H InChIKeys diverge
    fixed_h_keys = {c.fixed_h_inchi_key for c in ens.candidates}
    assert len(fixed_h_keys) == ens.total_generated

    # Canonical selection check
    assert ens.canonical_tautomer_id is not None
    canonical_candidates = [c for c in ens.candidates if c.is_canonical]
    assert len(canonical_candidates) == 1
    assert canonical_candidates[0].candidate_id == ens.canonical_tautomer_id


def test_ghost_atom_bsse_exclusion():
    """REQ-TOPOS-014.4: Verify ghost atoms (Z=0, symbol 'Gh') are assigned 0.0 Da and 0.0 A

    without invoking mendeleev, and excluded from SMIRKS reaction graphs and InChI calculation [M][D].
    """
    bsse_water = TopologyInput(
        molecule_id="bsse_water_dimer",
        smiles="O.[*]",
        elements=["O", "H", "H", "Gh"],
        atomic_numbers=[8, 1, 1, 0],
        is_ghost=[False, False, False, True],
    )
    assert bsse_water.is_ghost[3] is True
    assert bsse_water.masses[3] == 0.0

    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(bsse_water, config)
    # Ghost atom did not cause crash, valid ensemble produced with valid 27-char InChIKeys
    assert ens.total_generated >= 1
    for c in ens.candidates:
        assert len(c.inchi_key) == 27
        assert len(c.fixed_h_inchi_key) == 27


def test_qm_handshake_and_thermodynamic_filtering(tmp_path):
    """REQ-TOPOS-014.5: Verify 3D conformer generation (ETKDGv3) and thermodynamic pre-filtering adapter [M][D]."""
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2, energy_cutoff_kcal_mol=15.0)
    ens = enumerate_tautomers(acac, config)

    filtered_ens = filter_tautomers_thermodynamics(ens, config, scratch_dir=tmp_path)
    assert filtered_ens.total_generated >= 1
    for c in filtered_ens.candidates:
        if c.relative_energy_kcal_mol is not None:
            assert c.relative_energy_kcal_mol <= config.energy_cutoff_kcal_mol + 1e-4


def test_hdf5_threadsafe_concurrency_persistence(tmp_path):
    """REQ-TOPOS-014.6: Verify thread-safe and process-safe HDF5 persistence under filelock [M][D]."""
    h5_file = tmp_path / "tautomer_archive.h5"
    acac = TopologyInput(
        molecule_id="acac_persisted",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(acac, config)

    # Save to HDF5
    saved_path = save_tautomer_ensemble_to_hdf5(ens, h5_file)
    assert saved_path.exists()

    # Load from HDF5
    loaded_ens = load_tautomer_ensemble_from_hdf5(h5_file, molecule_id="acac_persisted")
    assert loaded_ens.parent_id == ens.parent_id
    assert loaded_ens.total_generated == ens.total_generated
    assert loaded_ens.canonical_tautomer_id == ens.canonical_tautomer_id

    # Verify fixed-width datatypes
    with h5py.File(h5_file, "r") as f:
        grp = f[f"/tautomers/{ens.parent_id}"]
        assert "smiles" in grp
        assert "fixed_h_inchi_key" in grp
        assert "canonical_score" in grp
        assert grp["smiles"].dtype.kind == "S" or grp["smiles"].dtype.metadata is not None


def test_dynamic_mendeleev_mass_invariants():
    """Anti-Spoofing & Mendeleev Mandate: Verify non-ghost masses are dynamically queried from Mendeleev [M][D]."""
    top = TopologyInput(
        molecule_id="dyn_mass_test",
        elements=["C", "O", "N", "Gh"],
        atomic_numbers=[6, 8, 7, 0],
        bonds=[(0, 1, 1.0), (0, 2, 1.0)],
    )
    # Check dynamic mendeleev values against live library
    assert np.isclose(top.masses[0], float(element(6).mass), atol=1e-4)
    assert np.isclose(top.masses[1], float(element(8).mass), atol=1e-4)
    assert np.isclose(top.masses[2], float(element(7).mass), atol=1e-4)
    assert top.masses[3] == 0.0


def test_invalid_topology_input_handling():
    """REQ-TOPOS-014.1: Verify InvalidTopologyInputError on malformed SMILES [M][D]."""
    with pytest.raises(InvalidTopologyInputError):
        top_bad = TopologyInput(
            molecule_id="bad_smiles",
            smiles="INVALID_SMILES_STRING_NOT_CHEMICAL",
            elements=["C"],
            atomic_numbers=[6],
        )
        config = TautomerEnumerationConfig()
        enumerate_tautomers(top_bad, config)


def test_all_ghost_atoms_raises_sanitization_error():
    """REQ-TOPOS-014.4: Verify GhostAtomSanitizationError when topology has only ghost atoms [M][D]."""
    all_ghosts = TopologyInput(
        molecule_id="only_ghosts",
        smiles="[*].[*]",
        elements=["Gh", "Gh"],
        atomic_numbers=[0, 0],
        is_ghost=[True, True],
    )
    config = TautomerEnumerationConfig()
    with pytest.raises(GhostAtomSanitizationError):
        enumerate_tautomers(all_ghosts, config)


def test_tautomer_storage_lock_timeout(tmp_path):
    """REQ-TOPOS-014.6: Verify TautomerStorageLockTimeoutError when lock cannot be acquired [M][D]."""
    h5_file = tmp_path / "locked_archive.h5"
    lock_file = h5_file.with_suffix(".h5.lock")

    ens = TautomerEnsemble(
        parent_id="lock_test",
        canonical_tautomer_id="c1",
        total_generated=1,
        candidates=[
            TautomerCandidate(
                candidate_id="c1",
                smiles="O",
                inchi_key="XLYOFNOQVPJJNP-UHFFFAOYSA-N",
                fixed_h_inchi_key="XLYOFNOQVPJJNP-UHFFFAOYNA-N",
                canonical_score=0.0,
                is_canonical=True,
                transform_depth=0,
            )
        ],
        execution_duration_seconds=0.01,
    )

    # Ensure archive file exists so load attempts lock acquisition rather than missing file check
    h5_file.touch()

    # Acquire lock externally to simulate locked condition
    external_lock = filelock.FileLock(str(lock_file))
    with external_lock.acquire():
        # Physically calling save under locked condition must raise TautomerStorageLockTimeoutError
        with pytest.raises(TautomerStorageLockTimeoutError):
            save_tautomer_ensemble_to_hdf5(ens, h5_file, lock_timeout=0.05)

        # Physically calling load under locked condition must raise TautomerStorageLockTimeoutError
        with pytest.raises(TautomerStorageLockTimeoutError):
            load_tautomer_ensemble_from_hdf5(h5_file, "lock_test", lock_timeout=0.05)


def test_tautomer_persistence_error_missing_file_and_group(tmp_path):
    """REQ-TOPOS-014.6: Verify TautomerPersistenceError on missing archive or missing molecule ID [M][D]."""
    missing_file = tmp_path / "nonexistent.h5"
    with pytest.raises(TautomerPersistenceError):
        load_tautomer_ensemble_from_hdf5(missing_file, "mol_missing")

    # Create empty HDF5
    existing_file = tmp_path / "empty.h5"
    with h5py.File(existing_file, "w") as f:
        f.create_group("/other_group")

    with pytest.raises(TautomerPersistenceError):
        load_tautomer_ensemble_from_hdf5(existing_file, "mol_not_present")


def test_pydantic_validation_invariants():
    """Verify strict Pydantic v2 validation rules and error contracts across all domain models [M][D]."""
    # 1. TopologyInput missing all structural inputs
    with pytest.raises(ValidationError):
        TopologyInput(
            molecule_id="empty",
            elements=["C"],
            atomic_numbers=[6],
        )

    # 2. TopologyInput length mismatch
    with pytest.raises(ValidationError):
        TopologyInput(
            molecule_id="mismatch",
            smiles="C",
            elements=["C", "C"],
            atomic_numbers=[6],
        )

    # 3. TautomerEnsemble canonical count != 1
    with pytest.raises(ValidationError):
        TautomerEnsemble(
            parent_id="ens_bad",
            canonical_tautomer_id="c1",
            total_generated=1,
            candidates=[
                TautomerCandidate(
                    candidate_id="c1",
                    smiles="C",
                    inchi_key="VNWKTokens",
                    fixed_h_inchi_key="VNWKTokens",
                    canonical_score=0.0,
                    is_canonical=False,  # Should be True!
                    transform_depth=0,
                )
            ],
            execution_duration_seconds=0.01,
        )


def test_valence_conservation_and_exception_hierarchy():
    """Verify domain exception hierarchy and ValenceConservationError properties [M][D]."""
    assert issubclass(TautomerEnumerationTimeoutError, ToposPerceptionError)
    assert issubclass(TautomerCombinatorialLimitExceededError, ToposPerceptionError)
    assert issubclass(ValenceConservationError, ToposPerceptionError)
    assert issubclass(InvalidTopologyInputError, ToposPerceptionError)
    assert issubclass(TautomerCanonicalizationError, ToposPerceptionError)
    assert issubclass(TautomerPersistenceError, ToposPerceptionError)
    assert issubclass(TautomerStorageLockTimeoutError, ToposPerceptionError)
    assert issubclass(QuantumChemistryHandshakeError, ToposPerceptionError)
    assert issubclass(GhostAtomSanitizationError, ToposPerceptionError)

    val_err = ValenceConservationError("Valence octet exceeded")
    assert "Valence octet exceeded" in str(val_err)
    assert isinstance(val_err, ToposPerceptionError)


def test_3d_coordinate_reconstruction_and_covalent_radii():
    """REQ-TOPOS-014.1: Verify 3D coordinate connectivity perception via Pyykkö covalent radii [M][D]."""
    coords = [
        (0.0, 0.0, 0.0),      # O1
        (0.757, 0.586, 0.0),  # H2
        (-0.757, 0.586, 0.0), # H3
        (3.0, 0.0, 0.0),      # Gh4 (BSSE ghost atom)
    ]
    top_3d = TopologyInput(
        molecule_id="water_3d_bsse",
        elements=["O", "H", "H", "Gh"],
        atomic_numbers=[8, 1, 1, 0],
        coordinates=coords,
        is_ghost=[False, False, False, True],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(top_3d, config)
    assert ens.total_generated >= 1
    assert ens.candidates[0].fixed_h_inchi_key is not None
    assert len(ens.candidates[0].fixed_h_inchi_key) == 27


Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.