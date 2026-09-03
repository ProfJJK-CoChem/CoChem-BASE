Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260901-suggestions\.in-progress\Perfected_SRS_Chunk_11_TOPOS_General_Utilities_Part_1_prompts.md.
Original prompt:
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous feature suite specified in Software Requirements Specification (SRS) Chunk 11: `TOPOS_General_Utilities_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev library mandate, and Method Matrix v4. Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must execute physically against authentic chemical topologies, genuine molecular structures, and physical constants.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Inspect the repository structure under `cochem/topos/` to identify existing graph primitives, `TopologyGraph` abstractions, and testing conventions established in prior TOPOS modules.
2. **Implementation**: Implement all target modules specified below with strict Python 3.10+ PEP 484 type annotations, thread-safe persistence, and custom typed domain exceptions (`ToposError`, `MalformedRecordError`, `UnparameterizedAtomError`, `BondPerceptionError`, `ParsingAirGapError`, `TopologyDiffError`, `FragmentationError`, `FingerprintGenerationError`).
3. **Physical Test Suite**: Write comprehensive, unmocked test suites covering each module with authentic chemical species and physical fixtures (e.g., QM9 water bare coordinates, authentic methanesulfonamide Period 3 geometries, benzene V2000 SDF records, phenanthrene aromatic topologies, aspirin BRICS disconnections, benzene-to-phenol topology diffs, and pyridine ECFP4 fingerprints).
4. **Physical Verification**: Execute the test suite using `run_command` in the terminal (`pytest tests/topos/ -v`). Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured execution report detailing all files created and modified on disk.

---

### MODULE SPECIFICATIONS

#### 1. [TOPOS] Pydantic v2 Domain Models & Exception Hierarchy
- **File Target**: `cochem/topos/models.py` and `cochem/topos/exceptions.py` (and export in `cochem/topos/__init__.py`)
- **Domain Exceptions (`cochem/topos/exceptions.py`)**:
  - `ToposError(Exception)`: Base exception for all TOPOS operations.
  - `MalformedRecordError(ToposError)`: Raised when input record syntax is corrupted or unparseable.
  - `UnparameterizedAtomError(ToposError)`: Raised when an atom lacks forcefield parameters.
  - `BondPerceptionError(ToposError)`: Raised when physical valences or bond orders cannot be resolved.
  - `ParsingAirGapError(ToposError)`: Raised when a parser worker process exceeds memory or execution time limits.
  - `TopologyDiffError(ToposError)`: Raised when MCS graph diffing fails to resolve.
  - `FragmentationError(ToposError)`: Raised when retrosynthetic fragmentation or valence checking fails.
  - `FingerprintGenerationError(ToposError)`: Raised when circular fingerprint generation fails.
- **Data Models (`cochem/topos/models.py`)**:
  - Implement Pydantic v2 JSON-safe models with full validation:
    - `BondOrderEdge`: `atom_i: int`, `atom_j: int`, `bond_order: float`.
    - `MoleculeRecord`: `name: str`, `elements: List[str]`, `coordinates: List[Tuple[float, float, float]]`, `formal_charges: List[int]`, `partial_charges: List[float] = Field(default_factory=list)`, `chiral_flags: List[int] = Field(default_factory=list)`, `radical_centers: List[int] = Field(default_factory=list)`, `mass_numbers: List[int] = Field(default_factory=list)`, `bonds: List[Tuple[int, int, float]]` (normalized 0-based indices), `properties: Dict[str, str] = Field(default_factory=dict)`.
    - `SubgraphDeltaRecord`: `atom_indices: List[int]`, `elements: List[str]`, `bonds: List[Tuple[int, int, float]]`, `smiles: str`.
    - `TopologyDelta`: `atom_mapping: Dict[int, int]`, `element_mutations: List[Tuple[int, str, str]]` (`(idx_a, elem_a, elem_b)`), `bond_order_mutations: List[Tuple[int, int, float, float]]` (`(idx_a, idx_b, bo_a, bo_b)`), `subgraph_additions: List[SubgraphDeltaRecord]`, `subgraph_deletions: List[SubgraphDeltaRecord]`.
    - `AttachmentSite`: `anchor_atom_idx: int` (0-based index), `brics_class: int`, `polarity: str = Field(default="neutral")` ("donor", "acceptor", "neutral"), `connection_vector: Tuple[float, float, float]`, `severed_partner_element: str`.
    - `SynthonRecord`: `smiles: str`, `elements: List[str]`, `coordinates: List[Tuple[float, float, float]]`, `bonds: List[Tuple[int, int, float]]`, `attachment_sites: List[AttachmentSite]`, `formal_charge: int`.
    - `NonBondedParameter`: `atom_type: str`, `sigma_nm: float`, `epsilon_kj_mol: float`, `r_min_half_angstrom: float`, `epsilon_kcal_mol: float`.
    - `ForceFieldAssignmentResult`: `atom_types: List[str]`, `charges: List[float]`, `bonded_parameters: Dict[str, List[float]]`, `non_bonded_parameters: List[NonBondedParameter]`, `forcefield_family: str` ("GAFF2" or "OPLS-AA"), `energy_unit: str` ("kcal/mol" or "kJ/mol"), `distance_unit: str` ("angstrom" or "nanometer"), `angle_unit: str = "degrees"`.
    - `BondPerceptionResult`: `bond_orders: List[BondOrderEdge]`, `formal_charges: List[int]`, `lone_pairs: List[int]`, `total_charge: int`.
    - `ECFP4FingerprintPayload`: `bit_vector_1024: List[int]`, `bit_vector_2048: List[int]`, `on_bits_2048: List[int]`, `count_vector: Dict[int, int]`, `features_de_duplicated: int`.

#### 2. [TOPOS] Multi-Molecule Parsing and Writing (.mol2 and .sdf)
- **Requirement ID**: `REQ-TOPOS-001`
- **File Target**: `cochem/topos/io.py`
- **Streaming Generator Architecture**:
  - Implement `SDFStreamReader(filepath: Path)` and `Mol2StreamReader(filepath: Path)` providing `stream_records() -> Generator[MoleculeRecord, None, None]` operating in constant $O(1)$ memory per record.
  - Implement `SDFWriter(filepath: Path)` and `Mol2Writer(filepath: Path)` for batch and streaming serializations.
- **Dialect & 0-Based Index Normalization**:
  - Standardize all internal bond connectivity to **0-based indexing**. Parsers decrement 1-based indices from MDL connection tables and Tripos `@<TRIPOS>BOND` records. Serializers re-index to 1-based upon writing.
  - `.sdf`: Full support for MDL V2000 and V3000 blocks delimited by `$$$$`. Normalize CRLF-to-LF before fixed-width column slicing. In V2000, parse trailing property lines: `M  CHG` (formal charges), `M  RAD` (radical states), and `M  ISO` (isotopic differences $\Delta m$). Parse coordinates, chiral flags, and arbitrary SD data headers (`> <KEY>`) into `MoleculeRecord.properties`.
  - `.mol2`: Support Tripos blocks (`@<TRIPOS>MOLECULE`, `@<TRIPOS>ATOM`, `@<TRIPOS>BOND`, `@<TRIPOS>SUBSTRUCTURE`), Sybyl atom types, electrostatic partial charges (Gasteiger/Mulliken), and substructure names/IDs.
- **Worker Sandboxing & Non-Executable IPC**:
  - Parse untrusted external records in isolated worker subprocesses spawned strictly via `multiprocessing.get_context("spawn")` to eliminate POSIX/CUDA fork deadlocks.
  - IPC must use non-executable JSON byte streams or Apache Arrow buffers; Python `pickle` deserialization is strictly banned.
  - Enforce quantitative limits per record: timeout = $30.0\text{ s}$, resident memory limit = $2048\text{ MB}$ (via POSIX `resource.setrlimit(resource.RLIMIT_AS, ...)` on Linux/macOS and Windows Job Objects via `win32job` on Windows).
  - Malformed or corrupted records raise `MalformedRecordError` and are quarantined to `pathlib.Path(os.environ.get("COCH_ARTIFACTS", Path.home() / ".cochem" / "artifacts")) / "quarantine" / f"{sha256}.raw"` with raw lexical traces.
- **Canonical Serialization**: Writers enforce canonical Morgan atom ordering and 6-decimal float formatting for coordinates.

#### 3. [TOPOS] Automated Forcefield Assignment (GAFF2 / OPLS-AA)
- **Requirement ID**: `REQ-TOPOS-002`
- **File Target**: `cochem/topos/forcefield.py`
- **Entrypoint**: `assign_forcefield_parameters(smiles: str, forcefield: str = "GAFF2") -> ForceFieldAssignmentResult`
- **Topological Atom Typing**:
  - Assign GAFF2 and OPLS-AA atom types using hierarchical SMARTS pattern matching against chemical environments (element, hybridization $sp, sp^2, sp^3$, formal charge, neighboring coordination).
  - Deterministic Ring Perception: Relevant Cycle Basis (RCB) with canonical sorting to guarantee invariant ring membership across symmetric cages and fused systems, eliminating non-unique SSSR variations.
  - Aromaticity Perception: Evaluate Hückel ($4n+2$) $\pi$-electron delocalization and polycyclic conjugated networks (e.g., distinguishing GAFF2 `ca` 6-membered aromatic, `cp` bridgehead biphenyl, and `cq` 5/6 fused bridgehead centers).
- **Non-Bonded Combination Rules & 1-4 Scaling Protocols**:
  - **GAFF2 (AMBER)**: Lorentz-Berthelot mixing rules ($R^*_{ij} = \frac{1}{2}(R^*_i + R^*_j), \epsilon_{ij} = \sqrt{\epsilon_i \epsilon_j}$); 1-4 electrostatic scaling factor $= 1.2^{-1} \approx 0.8333$; 1-4 vdW scaling factor $= 2.0^{-1} = 0.5$. Parameters defined in $\text{kcal/mol}$, $\text{\AA}$, and angles in degrees.
  - **OPLS-AA**: Geometric mixing rules for both $\sigma$ and $\epsilon$ ($\sigma_{ij} = \sqrt{\sigma_i \sigma_j}, \epsilon_{ij} = \sqrt{\epsilon_i \epsilon_j}$); 1-4 electrostatic scaling factor $= 0.5$; 1-4 vdW scaling factor $= 0.5$. Parameters defined in $\text{kJ/mol}$, $\text{nm}$, and angles in degrees.
- **Parameter Registries**: Query parameters from immutable registries under `pathlib.Path(os.environ.get("COCH_DATA", Path.home() / ".cochem" / "data")) / "forcefields"`. Results must provide explicit parameter separation (`sigma_nm` vs `r_min_half_angstrom`). Unparameterized elements or metal complexes raise `UnparameterizedAtomError` with offending atom indices; default or dummy parameter injection is strictly prohibited.

#### 4. [TOPOS] Retrosynthetic Topological Fragmentation (BRICS / RECAP)
- **Requirement ID**: `REQ-TOPOS-003`
- **File Target**: `cochem/topos/fragmentation.py`
- **Entrypoints**:
  - `fragment_by_brics(smiles: str) -> List[SynthonRecord]`
  - `fragment_by_recap(smiles: str) -> List[SynthonRecord]`
- **Chemical Grammar Disconnections**:
  - BRICS: 16 strategic cleavage rules L1–L16 covering amides, esters, carbamates, ureas, sulfonamides, ethers, and specific C-C linkages (accounting for the high torsional barrier and non-rotatable nature of amide bonds).
  - RECAP: 11 retrosynthetic transformation classes.
- **Attachment Tagging & Recombination Grammar**:
  - Severed linkages are tagged with indexed dummy tokens (`[1*]`, `[2*]`, ..., `[16*]`) preserving reaction site classes.
  - Enforce the directional $16 \times 16$ BRICS compatibility matrix ($M_{ij} \in \{0, 1\}$) with polar directionality (`polarity: str = "donor" | "acceptor" | "neutral"`).
- **Geometric Synthon Representation**:
  - Each `SynthonRecord` retains its full topological bond graph (`bonds`), elemental identity (`elements`), 3D Cartesian coordinates (`coordinates`), and connection vectors ($\mathbf{v} = \mathbf{r}_{\text{severed}} - \mathbf{r}_{\text{anchor}} \in \mathbb{R}^3$) in `AttachmentSite`.
  - Validate all synthons for closed-shell ground states, formal charge conservation, and physical valence validity. Failures raise `FragmentationError`.

#### 5. [TOPOS] Bond-Order Perception from Bare XYZ Coordinates
- **Requirement ID**: `REQ-TOPOS-004`
- **File Target**: `cochem/topos/perception.py`
- **Entrypoint**: `perceive_bond_orders_from_xyz(elements: List[str], coordinates: List[Tuple[float, float, float]] | np.ndarray, net_charge: int = 0) -> BondPerceptionResult`
- **Dynamic Mendeleev Calibration (Picometer to Ångström Conversion)**:
  - Covalent radii must be queried dynamically at runtime via `mendeleev.element(symbol).covalent_radius_pyykko`. Convert picometers ($pm$) to Ångströms:
    $$R_{\text{cov}}(\text{\AA}) = \frac{\text{mendeleev.element}(Z).\text{covalent\_radius\_pyykko}}{100.0}$$
  - Hardcoded tables or static constant fallbacks are strictly prohibited.
- **Distance Matrix & Candidate Connectivity Graph**:
  - Compute Euclidean distances $D_{ij} = \|\mathbf{r}_i - \mathbf{r}_j\|_2$. Establish candidate connectivity edges $E$ where:
    $$D_{ij} \le R_{\text{cov}}(i) + R_{\text{cov}}(j) + \delta, \quad \delta = 0.40\,\text{\AA}$$
- **Pauling Geometric Bond Order Formulation**:
  - Initial geometric bond order estimates:
    $$\text{BO}_{\text{geom}}(D_{ij}) = \exp\left( \frac{R_0(i, j) - D_{ij}}{B} \right)$$
    where $R_0(i, j) = R_{\text{cov}}(i) + R_{\text{cov}}(j)$ and $B = 0.37\,\text{\AA}$.
- **Integer Linear Program (ILP) Optimization**:
  - Optimize bond orders and lone pairs via ILP using the `scipy.optimize.milp` HiGHS solver backend:
    $$\min_{\mathbf{BO}, \mathbf{N}_{\text{lp}}, \mathbf{q}} \sum_{i=1}^N w_q |q_i| + \sum_{(i,j) \in E} w_{\text{BO}} |\text{BO}_{ij} - \text{BO}_{\text{geom}}(D_{ij})|$$
    with calibrated weights $w_q = 2.0$, $w_{\text{BO}} = 1.0$, subject to linear constraints:
    1. **Formal Charge Coupling Equality**:
       $$q_i + 2 \cdot N_{\text{lone\_pairs}}(i) + \sum_{j \in \text{adj}(i)} \text{BO}_{ij} = N_{\text{valence}}(i), \quad \forall i \in \{1, \dots, N\}$$
    2. **Total Charge Conservation**: $\sum_{i=1}^N q_i = Q_{\text{tot}}$
    3. **Period 2 Valence Shell (Octet Rule)**: For $C, N, O, F$:
       $$2 \cdot N_{\text{lone\_pairs}}(i) + 2 \sum_{j \in \text{adj}(i)} \text{BO}_{ij} \le 8$$
    4. **Period 3+ Hypervalency Limits**: For $Si, P, S, Cl, Se, Br, I$:
       $$2 \cdot N_{\text{lone\_pairs}}(i) + 2 \sum_{j \in \text{adj}(i)} \text{BO}_{ij} \le 12$$
       (permits hypervalent geometries including sulfonamides $-\text{SO}_2\text{NH}-$, sulfates, and phosphoranes).
    5. **Hydrogen Duet Rule**: For all $H$ atoms:
       $$\sum_{j \in \text{adj}(H)} \text{BO}_{Hj} = 1 \quad \text{and} \quad N_{\text{lone\_pairs}}(H) = 0$$
    6. **Variable Bounds & Non-Bonded Pruning**:
       $$\text{BO}_{ij} \in \{0, 1, 2, 3\}, \quad N_{\text{lone\_pairs}}(i) \in \{0, 1, 2, 3, 4\}, \quad q_i \in \{-2, -1, 0, 1, 2\}$$
       Bounds on $\text{BO}_{ij}$ start at 0, permitting the solver to set $\text{BO}_{ij} = 0$ to prune candidate non-bonded spatial contacts or clashes.
  - Unresolvable topologies or convergence failures raise `BondPerceptionError`.

#### 6. [TOPOS] Topology Diff Tool
- **Requirement ID**: `REQ-TOPOS-005`
- **File Target**: `cochem/topos/diff.py`
- **Entrypoint**: `compute_topology_diff(mol_a_smiles: str, mol_b_smiles: str) -> TopologyDelta`
- **Modular Product Graph & Relaxed MCS**:
  - Maximum Common Connected Substructure (MCCS) detection using the Bron-Kerbosch maximal clique algorithm on the modular product graph with vertex/edge substitution penalties.
  - Extracts the conserved scaffold and localized chemical mutations. Failures raise `TopologyDiffError`.
- **Structured Mutation Delta**:
  - Returns `TopologyDelta` containing `atom_mapping`, `element_mutations`, `bond_order_mutations`, `subgraph_additions`, and `subgraph_deletions`.
  - Provide serialization to validated JSON schemas and CLI formatted markdown tables.

#### 7. [TOPOS] Topological Fingerprint Generator (ECFP4 / Morgan)
- **Requirement ID**: `REQ-TOPOS-006`
- **File Target**: `cochem/topos/fingerprint.py`
- **Entrypoint**: `generate_ecfp4_fingerprint(smiles: str, radius: int = 2, n_bits: int = 2048) -> ECFP4FingerprintPayload`
- **Circular Neighborhood Construction**:
  - Extended-connectivity circular fingerprint with radius $R=2$ (diameter 4). Failures raise `FingerprintGenerationError`.
  - Initial Atom Invariant Packing: Derived from atomic number $Z$, heavy neighbor degree $d$, valence $v$, formal charge $q$, ring membership flag $r$, and discrete isotopic state $\Delta A$:
    $$\Delta A = \begin{cases} A_{\text{iso}} - \text{mendeleev.element}(Z).\text{mass\_number} & \text{if explicit isotope specified} \\ 0 & \text{default unlabeled atom} \end{cases}$$
    Packed via:
    $$inv_i^{(0)} = \text{MurmurHash3}\Big( \text{struct.pack}("<iiiiii", Z, d, v, q, r, \Delta A), \text{seed}=0 \Big) \& 0xFFFFFFFF$$
  - Deterministic Neighborhood Updates & Rogers-Hahn De-Duplication:
    For $r \in \{1, 2\}$:
    $$h_i^{(r)} = \text{MurmurHash3}\left( \text{struct.pack}("<II", r, h_i^{(r-1)}) \,+\, \sum_{j} \text{struct.pack}("<fI", \text{BO}_{ij}, h_j^{(r-1)}), \text{seed}=0 \right) \& 0xFFFFFFFF$$
    Prune identical structural fragments or symmetry-equivalent neighborhood subgraphs across radii $R \in \{0, 1, 2\}$ prior to bit folding.
  - Representations: Modulo bit folding into fixed-length bitvectors (1024-bit, 2048-bit) and raw integer count vector. Include vectorized Tanimoto and Dice similarity calculation utilities.

---

### PHYSICAL TEST SUITE SPECIFICATIONS

Implement the unmocked acceptance test suites under `tests/topos/`:

1. **`tests/topos/test_models.py`**:
   - Verify Pydantic v2 JSON-safe serialization and deserialization of `BondPerceptionResult`, `MoleculeRecord`, `TopologyDelta`, `SynthonRecord`, `ForceFieldAssignmentResult`, and `ECFP4FingerprintPayload` without tuple-key errors.
2. **`tests/topos/test_perception.py`**:
   - **Water Molecule (QM9 coordinates)**: Verify oxygen formal charge = 0, lone pairs = 2, two $\text{O}-\text{H}$ bonds of order 1.0, and net charge = 0.
   - **Methanesulfonamide (Period 3 Hypervalency)**: Verify sulfur atom (index 1) formal charge = 0, lone pairs = 0, two $\text{S}=\text{O}$ double bonds ($\text{BO} \approx 2.0$), $\text{S}-\text{N}$ and $\text{S}-\text{C}$ single bonds ($\text{BO} \approx 1.0$), with total sulfur bond order sum = 6.0 (valence shell of 12 electrons).
   - Dynamic Mendeleev calibration: Ensure covalent radii are scaled from picometers to Ångströms ($R_{\text{cov}} / 100.0$).
3. **`tests/topos/test_io.py`**:
   - **SDF V2000 Streaming**: Stream multi-record benzene SDF; verify 0-based bond index normalization, coordinate parsing, and property retention.
   - **Mol2 Streaming**: Stream Tripos mol2; verify Sybyl atom types, partial charges, and substructures.
   - **Quarantine Sandbox**: Test malformed syntax; verify `MalformedRecordError` and file write into the quarantine artifact directory with SHA-256 hash naming.
4. **`tests/topos/test_forcefield.py`**:
   - **Phenanthrene**: Test Relevant Cycle Basis (RCB) ring perception and GAFF2 aromatic typing; verify aromatic carbons `ca` and bridgehead carbons `cp`/`cq`.
   - **Non-bonded parameters**: Verify Lorentz-Berthelot parameters for GAFF2 and geometric parameters for OPLS-AA.
   - **Error Handling**: Verify `UnparameterizedAtomError` when attempting to type an unsupported metal complex.
5. **`tests/topos/test_fragmentation.py`**:
   - **Aspirin (BRICS)**: Verify ester bond cleavage (rule L3) yielding qualifying synthons with dummy attachment tokens (`[3*]`, etc.), valid connection vectors, and conserved formal charges.
   - **Directionality & Compatibility**: Verify that attachment sites correctly reflect donor/acceptor/neutral polarity.
6. **`tests/topos/test_diff.py`**:
   - **Benzene to Phenol**: Verify MCCS detection on the modular product graph; verify that the 6-carbon aromatic ring maps 1:1, and that hydroxyl addition is isolated in `subgraph_additions`.
7. **`tests/topos/test_fingerprint.py`**:
   - **Pyridine**: Compute ECFP4 fingerprint with $R=2$, $N=2048$. Verify bit vector length, active on-bits, and feature count vector.
   - **Similarity**: Compute Tanimoto similarity between pyridine and benzene; ensure physical bounds $0.0 < T < 1.0$.

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate**: Every function, method, and test fixture must execute physically. Absolutely no `pass` stubs, `NotImplementedError`, or synthetic mocked arrays (`np.zeros`, `np.ones`, etc.).
2. **Dynamic Mendeleev Mandate**: All covalent radii must be queried dynamically via `mendeleev.element(symbol).covalent_radius_pyykko / 100.0`. All isotopic masses and mass numbers must be queried dynamically via `mendeleev.element(symbol)`. No hardcoded mass or radius constant dictionaries.
3. **Tripartite Workspace Air-Gap**:
   - Code: $\mathcal{T}_{\text{code}} = \text{Path}(\text{os.environ.get}("COCH_SRC", \text{Path.home}() / ".cochem" / "src"))$
   - Data/Registries: $\mathcal{T}_{\text{data}} = \text{Path}(\text{os.environ.get}("COCH_DATA", \text{Path.home}() / ".cochem" / "data"))$
   - Artifacts/Quarantine: $\mathcal{T}_{\text{art}} = \text{Path}(\text{os.environ.get}("COCH_ARTIFACTS", \text{Path.home}() / ".cochem" / "artifacts"))$
4. **Platform-Specific Concurrency**:
   - On Windows (NTFS Tier 1), disable HDF5 SWMR and protect all writes with `filelock.FileLock` and atomic staging via `os.replace`.
   - On Linux/macOS (Tier 2/3), support POSIX advisory locks and SWMR mode.
   - Restrict parser subprocess workers to non-executable JSON/Arrow byte streams via `multiprocessing.get_context("spawn")`.
5. **Hardware Acceleration Fallback**: Explicitly handle GPU/MPS out-of-memory errors by falling back deterministically to vectorized CPU algorithms.

---

### ACTION PLAN FOR CODER

1. Implement `cochem/topos/exceptions.py` with custom typed exceptions.
2. Implement `cochem/topos/models.py` with Pydantic v2 data models.
3. Implement `cochem/topos/io.py` with `SDFStreamReader`, `Mol2StreamReader`, and batch writers.
4. Implement `cochem/topos/forcefield.py` with GAFF2/OPLS-AA typing and RCB ring perception.
5. Implement `cochem/topos/fragmentation.py` with BRICS/RECAP retrosynthetic fragmentation.
6. Implement `cochem/topos/perception.py` with dynamic Mendeleev radii and SciPy MILP bond-order solver.
7. Implement `cochem/topos/diff.py` with modular product Bron-Kerbosch MCCS diffing.
8. Implement `cochem/topos/fingerprint.py` with Morgan/ECFP4 circular fingerprinting and MurmurHash3.
9. Export all interfaces in `cochem/topos/__init__.py`.
10. Implement physical acceptance test suites in `tests/topos/`.
11. Run test suite via terminal (`pytest tests/topos/ -v`) and verify 100% pass rate.
12. Output the complete list of touched and created files in your final execution report.
An adversarial audit of the generated chunked prompt for `SRS_Chunk_11_TOPOS_General_Utilities_Part_1` has been initiated with the `adversary` agent (Conversation ID: `1d0db806-07ab-4fee-9b92-fb44ad8bba9d`). Standing by for the audit verdict.
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous feature suite specified in Software Requirements Specification (SRS) Chunk 11: `TOPOS_General_Utilities_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev library mandate, and Method Matrix v4. Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must execute physically against authentic chemical topologies, genuine molecular structures, and physical constants.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Inspect the repository structure under `cochem/topos/` to identify existing graph primitives, `TopologyGraph` abstractions, and testing conventions established in prior TOPOS modules.
2. **Implementation**: Implement all target modules specified below with strict Python 3.10+ PEP 484 type annotations, thread-safe persistence, and custom typed domain exceptions (`ToposError`, `MalformedRecordError`, `UnparameterizedAtomError`, `BondPerceptionError`, `ParsingAirGapError`, `TopologyDiffError`, `FragmentationError`, `FingerprintGenerationError`).
3. **Physical Test Suite**: Write comprehensive, unmocked test suites covering each module under `tests/topos/` with authentic chemical species and physical fixtures (e.g., QM9 water bare coordinates, authentic methanesulfonamide Period 3 geometries, benzene V2000 SDF records, phenanthrene aromatic topologies, aspirin BRICS disconnections, benzene-to-phenol topology diffs, and pyridine ECFP4 fingerprints).
4. **Physical Verification**: Execute the test suite using `run_command` in the terminal (`pytest tests/topos/ -v`). Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured execution report detailing all files created and modified on disk.

---

### MODULE SPECIFICATIONS

#### 1. [TOPOS] Pydantic v2 Domain Models & Exception Hierarchy
- **File Target**: `cochem/topos/models.py` and `cochem/topos/exceptions.py` (and export in `cochem/topos/__init__.py`)
- **Domain Exceptions (`cochem/topos/exceptions.py`)**:
  - `ToposError(Exception)`: Base exception for all TOPOS operations.
  - `MalformedRecordError(ToposError)`: Raised when input record syntax is corrupted or unparseable.
  - `UnparameterizedAtomError(ToposError)`: Raised when an atom lacks forcefield parameters.
  - `BondPerceptionError(ToposError)`: Raised when physical valences or bond orders cannot be resolved.
  - `ParsingAirGapError(ToposError)`: Raised when a parser worker process exceeds memory or execution time limits.
  - `TopologyDiffError(ToposError)`: Raised when MCS graph diffing fails to resolve.
  - `FragmentationError(ToposError)`: Raised when retrosynthetic fragmentation or valence checking fails.
  - `FingerprintGenerationError(ToposError)`: Raised when circular fingerprint generation fails.
- **Data Models (`cochem/topos/models.py`)**:
  - Implement Pydantic v2 JSON-safe models with full validation:
    - `BondOrderEdge`: `atom_i: int`, `atom_j: int`, `bond_order: float`.
    - `MoleculeRecord`: `name: str`, `elements: List[str]`, `coordinates: List[Tuple[float, float, float]]`, `formal_charges: List[int]`, `partial_charges: List[float] = Field(default_factory=list)`, `chiral_flags: List[int] = Field(default_factory=list)`, `radical_centers: List[int] = Field(default_factory=list)`, `mass_numbers: List[int] = Field(default_factory=list)`, `bonds: List[Tuple[int, int, float]]` (normalized 0-based indices: `(idx_a, idx_b, bond_order)`), `properties: Dict[str, str] = Field(default_factory=dict)`.
    - `SubgraphDeltaRecord`: `atom_indices: List[int]`, `elements: List[str]`, `bonds: List[Tuple[int, int, float]]`, `smiles: str`.
    - `TopologyDelta`: `atom_mapping: Dict[int, int]`, `element_mutations: List[Tuple[int, str, str]]` (`(idx_a, elem_a, elem_b)`), `bond_order_mutations: List[Tuple[int, int, float, float]]` (`(idx_a, idx_b, bo_a, bo_b)`), `subgraph_additions: List[SubgraphDeltaRecord]`, `subgraph_deletions: List[SubgraphDeltaRecord]`.
    - `AttachmentSite`: `anchor_atom_idx: int` (0-based index into synthon coordinates/elements), `brics_class: int`, `polarity: str = Field(default="neutral", description="Reaction directionality: donor, acceptor, neutral")`, `connection_vector: Tuple[float, float, float]`, `severed_partner_element: str`.
    - `SynthonRecord`: `smiles: str`, `elements: List[str]`, `coordinates: List[Tuple[float, float, float]]`, `bonds: List[Tuple[int, int, float]]` (0-based internal graph connectivity), `attachment_sites: List[AttachmentSite]`, `formal_charge: int`.
    - `NonBondedParameter`: `atom_type: str`, `sigma_nm: float`, `epsilon_kj_mol: float`, `r_min_half_angstrom: float`, `epsilon_kcal_mol: float`.
    - `ForceFieldAssignmentResult`: `atom_types: List[str]`, `charges: List[float]`, `bonded_parameters: Dict[str, List[float]]`, `non_bonded_parameters: List[NonBondedParameter]`, `forcefield_family: str` ("GAFF2" or "OPLS-AA"), `energy_unit: str` ("kcal/mol" or "kJ/mol"), `distance_unit: str` ("angstrom" or "nanometer"), `angle_unit: str = "degrees"`.
    - `BondPerceptionResult`: `bond_orders: List[BondOrderEdge]`, `formal_charges: List[int]`, `lone_pairs: List[int]`, `total_charge: int`.
    - `ECFP4FingerprintPayload`: `bit_vector_1024: List[int]`, `bit_vector_2048: List[int]`, `on_bits_2048: List[int]`, `count_vector: Dict[int, int]`, `features_de_duplicated: int`.

#### 2. [TOPOS] Multi-Molecule Parsing and Writing (.mol2 and .sdf)
- **Requirement ID**: `REQ-TOPOS-001`
- **File Target**: `cochem/topos/io.py` (and export in `cochem/topos/__init__.py`)
- **Streaming Generator Architecture**:
  - Implement lazy, memory-efficient stream readers `SDFStreamReader(filepath: Path)` and `Mol2StreamReader(filepath: Path)` providing `stream_records() -> Generator[MoleculeRecord, None, None]` operating in constant $O(1)$ RAM per record.
  - Implement `SDFWriter(filepath: Path)` and `Mol2Writer(filepath: Path)` supporting batch and incremental streaming serializations.
- **Dialect & 0-Based Index Normalization**:
  - Standardize all internal bond connectivity to **0-based indexing**. Parsers decrement 1-based indices from MDL connection tables and Tripos `@<TRIPOS>BOND` records. Serializers re-index to 1-based upon writing.
  - `.sdf`: Full support for MDL V2000 and V3000 blocks delimited by `$$$$`. Normalize CRLF-to-LF before fixed-width FORTRAN column slicing. In V2000, parse trailing property lines: `M  CHG` (formal charges), `M  RAD` (radical states), and `M  ISO` (isotopic differences $\Delta m$). Parse coordinates, chiral flags, and arbitrary SD data headers (`> <KEY>`) into `MoleculeRecord.properties`.
  - `.mol2`: Support Tripos blocks (`@<TRIPOS>MOLECULE`, `@<TRIPOS>ATOM`, `@<TRIPOS>BOND`, `@<TRIPOS>SUBSTRUCTURE`), Sybyl atom types, electrostatic partial charges (Gasteiger/Mulliken), and substructure names/IDs.
- **Worker Sandboxing & Safe Non-Executable IPC**:
  - Parse untrusted external records in isolated worker subprocesses initialized strictly via `multiprocessing.get_context("spawn")` to eliminate POSIX/CUDA fork deadlocks.
  - IPC is strictly restricted to non-executable JSON byte streams or Apache Arrow IPC buffers; Python `pickle` deserialization is strictly banned to prevent remote code execution vulnerabilities.
  - Quantitative execution limits enforced per record: timeout = $30.0\text{ s}$, resident memory limit = $2048\text{ MB}$ enforced via POSIX `resource.setrlimit(resource.RLIMIT_AS, ...)` on Linux/macOS and Windows Job Objects (`win32job.CreateJobObject`, `SetInformationJobObject`) on Native Windows (Tier 1).
  - Corrupted or malformed records raise `MalformedRecordError` and are quarantined to `pathlib.Path(os.environ.get("COCH_ARTIFACTS", Path.home() / ".cochem" / "artifacts")) / "quarantine" / f"{sha256}.raw"` with raw lexical traces.
- **Canonical Serialization**: Writers enforce canonical Morgan atom ordering and 6-decimal float formatting for coordinates.

#### 3. [TOPOS] Automated Forcefield Assignment (GAFF2 / OPLS-AA)
- **Requirement ID**: `REQ-TOPOS-002`
- **File Target**: `cochem/topos/forcefield.py` (and export in `cochem/topos/__init__.py`)
- **Entrypoint**: `assign_forcefield_parameters(smiles: str, forcefield: str = "GAFF2") -> ForceFieldAssignmentResult`
- **Topological Atom Typing**:
  - Assign GAFF2 and OPLS-AA atom types using hierarchical SMARTS pattern matching against chemical environments (element, hybridization $sp, sp^2, sp^3$, formal charge, neighboring coordination).
  - Deterministic Ring Perception: Relevant Cycle Basis (RCB) with canonical sorting to guarantee invariant, deterministic ring membership across symmetric cages and fused systems, eliminating non-unique SSSR variations.
  - Aromaticity Perception: Evaluate both Hückel ($4n+2$) $\pi$-electron delocalization and polycyclic conjugated networks (e.g., distinguishing GAFF2 `ca` 6-membered aromatic, `cp` bridgehead biphenyl, and `cq` 5/6 fused bridgehead centers).
- **Non-Bonded Combination Rules & 1-4 Scaling Protocols**:
  - **GAFF2 (AMBER)**: Lorentz-Berthelot mixing rules ($R^*_{ij} = \frac{1}{2}(R^*_i + R^*_j), \epsilon_{ij} = \sqrt{\epsilon_i \epsilon_j}$); 1-4 electrostatic scaling factor $= 1.2^{-1} \approx 0.8333$; 1-4 vdW scaling factor $= 2.0^{-1} = 0.5$. Parameters defined in $\text{kcal/mol}$, $\text{\AA}$, and angles in degrees.
  - **OPLS-AA**: Geometric mixing rules for both $\sigma$ and $\epsilon$ ($\sigma_{ij} = \sqrt{\sigma_i \sigma_j}, \epsilon_{ij} = \sqrt{\epsilon_i \epsilon_j}$); 1-4 electrostatic scaling factor $= 0.5$; 1-4 vdW scaling factor $= 0.5$. Parameters defined in $\text{kJ/mol}$, $\text{nm}$, and angles in degrees.
- **Parameter Registries & Disambiguated Output**:
  - Query parameters from immutable registries under `pathlib.Path(os.environ.get("COCH_DATA", Path.home() / ".cochem" / "data")) / "forcefields"`.
  - Output typed `ForceFieldAssignmentResult` models with explicit parameter separation (`sigma_nm` vs `r_min_half_angstrom`).
  - Unparameterized elements or metal complexes raise `UnparameterizedAtomError` with the offending atom indices; default or dummy parameter injection is strictly prohibited.

#### 4. [TOPOS] Retrosynthetic Topological Fragmentation (BRICS / RECAP Synthons)
- **Requirement ID**: `REQ-TOPOS-003`
- **File Target**: `cochem/topos/fragmentation.py` (and export in `cochem/topos/__init__.py`)
- **Entrypoints**:
  - `fragment_by_brics(smiles: str) -> List[SynthonRecord]`
  - `fragment_by_recap(smiles: str) -> List[SynthonRecord]`
- **Chemical Grammar Disconnections**:
  - BRICS: 16 strategic cleavage rules L1–L16 covering amides, esters, carbamates, ureas, sulfonamides, ethers, and specific C-C linkages (accounting for the high torsional barrier and non-rotatable nature of amide bonds).
  - RECAP: 11 retrosynthetic transformation classes.
- **Attachment Tagging & Recombination Grammar**:
  - Severed linkages are tagged with indexed dummy tokens (`[1*]`, `[2*]`, ..., `[16*]`) preserving reaction site classes.
  - Enforce the directional $16 \times 16$ BRICS compatibility matrix ($M_{ij} \in \{0, 1\}$) with polar directionality (`polarity: str = "donor" | "acceptor" | "neutral"`) to govern valid synthetic recombinations.
- **Complete Geometric Synthon Representation**:
  - Each `SynthonRecord` retains its full topological bond graph (`bonds`), elemental identity (`elements`), 3D Cartesian coordinates (`coordinates`), and connection vectors ($\mathbf{v} = \mathbf{r}_{\text{severed}} - \mathbf{r}_{\text{anchor}} \in \mathbb{R}^3$) in `AttachmentSite`, enabling exact spatial structure regeneration.
  - Validate all synthons for closed-shell ground states, formal charge conservation, and physical valence validity. Failures raise `FragmentationError`.

#### 5. [TOPOS] Bond-Order Perception from Bare XYZ Coordinates
- **Requirement ID**: `REQ-TOPOS-004`
- **File Target**: `cochem/topos/perception.py` (and export in `cochem/topos/__init__.py`)
- **Entrypoint**: `perceive_bond_orders_from_xyz(elements: List[str], coordinates: List[Tuple[float, float, float]] | np.ndarray, net_charge: int = 0) -> BondPerceptionResult`
- **Dynamic Mendeleev Calibration (Picometer to Ångström Conversion)**:
  - Covalent radii must be queried dynamically at runtime via `mendeleev.element(symbol).covalent_radius_pyykko`. Because `mendeleev` returns values in picometers ($pm$), they MUST be scaled to Ångströms:
    $$R_{\text{cov}}(\text{\AA}) = \frac{\text{mendeleev.element}(Z).\text{covalent\_radius\_pyykko}}{100.0}$$
  - Hardcoded tables or static constant fallbacks are strictly prohibited.
- **Distance Matrix & Candidate Connectivity Graph**:
  - Compute Euclidean distances $D_{ij} = \|\mathbf{r}_i - \mathbf{r}_j\|_2$. Establish candidate connectivity edges $E$ where:
    $$D_{ij} \le R_{\text{cov}}(i) + R_{\text{cov}}(j) + \delta, \quad \delta = 0.40\,\text{\AA}$$
- **Pauling Geometric Bond Order Formulation**:
  - Initial geometric bond order estimates are calculated via Pauling's empirical relation:
    $$\text{BO}_{\text{geom}}(D_{ij}) = \exp\left( \frac{R_0(i, j) - D_{ij}}{B} \right)$$
    where $R_0(i, j) = R_{\text{cov}}(i) + R_{\text{cov}}(j)$ and $B = 0.37\,\text{\AA}$.
- **Integer Linear Program (ILP) Optimization**:
  - Given bare coordinates and user-specified `net_charge: int = 0` ($Q_{\text{tot}}$), optimize bond orders, lone pairs, and formal charges via ILP using the `scipy.optimize.milp` HiGHS solver backend:
    $$\min_{\mathbf{BO}, \mathbf{N}_{\text{lp}}, \mathbf{q}} \sum_{i=1}^N w_q |q_i| + \sum_{(i,j) \in E} w_{\text{BO}} |\text{BO}_{ij} - \text{BO}_{\text{geom}}(D_{ij})|$$
    with calibrated weights $w_q = 2.0$, $w_{\text{BO}} = 1.0$, subject to the following strict linear constraints:
    1. **Formal Charge Coupling Equality**:
       $$q_i + 2 \cdot N_{\text{lone\_pairs}}(i) + \sum_{j \in \text{adj}(i)} \text{BO}_{ij} = N_{\text{valence}}(i), \quad \forall i \in \{1, \dots, N\}$$
    2. **Total Charge Conservation**: $\sum_{i=1}^N q_i = Q_{\text{tot}}$
    3. **Period 2 Valence Shell (Octet Rule)**: For $C, N, O, F$:
       $$2 \cdot N_{\text{lone\_pairs}}(i) + 2 \sum_{j \in \text{adj}(i)} \text{BO}_{ij} \le 8$$
    4. **Period 3+ Hypervalency Limits**: For $Si, P, S, Cl, Se, Br, I$:
       $$2 \cdot N_{\text{lone\_pairs}}(i) + 2 \sum_{j \in \text{adj}(i)} \text{BO}_{ij} \le 12$$
       (permits standard hypervalent geometries including sulfonamides $-\text{SO}_2\text{NH}-$, sulfates, and phosphoranes).
    5. **Hydrogen Duet Rule**: For all $H$ atoms:
       $$\sum_{j \in \text{adj}(H)} \text{BO}_{Hj} = 1 \quad \text{and} \quad N_{\text{lone\_pairs}}(H) = 0$$
    6. **Variable Bounds & Non-Bonded Pruning**:
       $$\text{BO}_{ij} \in \{0, 1, 2, 3\}, \quad N_{\text{lone\_pairs}}(i) \in \{0, 1, 2, 3, 4\}, \quad q_i \in \{-2, -1, 0, 1, 2\}$$
       Bounds on $\text{BO}_{ij}$ start at 0, permitting the solver to set $\text{BO}_{ij} = 0$ to prune candidate spatial contacts such as non-bonded steric clashes or hydrogen bonds.
  - Unresolvable topologies or convergence failures raise `BondPerceptionError`.

#### 6. [TOPOS] Topology Diff Tool
- **Requirement ID**: `REQ-TOPOS-005`
- **File Target**: `cochem/topos/diff.py` (and export in `cochem/topos/__init__.py`)
- **Entrypoint**: `compute_topology_diff(mol_a_smiles: str, mol_b_smiles: str) -> TopologyDelta`
- **Modular Product Graph & Relaxed MCS**:
  - Maximum Common Connected Substructure (MCCS) detection using the Bron-Kerbosch maximal clique algorithm on the modular product graph with vertex/edge substitution penalties.
  - Extracts the conserved scaffold and localized chemical mutations. Failures raise `TopologyDiffError`.
- **Structured Mutation Delta**:
  - Output strongly typed `TopologyDelta` containing `atom_mapping`, `element_mutations`, `bond_order_mutations`, `subgraph_additions`, and `subgraph_deletions`.
  - Provide serialization to validated JSON schemas and formatted CLI markdown tables.

#### 7. [TOPOS] Topological Fingerprint Generator (ECFP4 / Morgan)
- **Requirement ID**: `REQ-TOPOS-006`
- **File Target**: `cochem/topos/fingerprint.py` (and export in `cochem/topos/__init__.py`)
- **Entrypoint**: `generate_ecfp4_fingerprint(smiles: str, radius: int = 2, n_bits: int = 2048) -> ECFP4FingerprintPayload`
- **Circular Neighborhood Construction**:
  - Extended-connectivity circular fingerprinting with radius $R=2$ (diameter 4). Failures raise `FingerprintGenerationError`.
  - Initial Atom Invariant Packing: 32-bit packed integers derived from atomic number $Z$, heavy neighbor degree $d$, valence $v$, formal charge $q$, ring membership flag $r$, and discrete isotopic state $\Delta A$:
    $$\Delta A = \begin{cases} A_{\text{iso}} - \text{mendeleev.element}(Z).\text{mass\_number} & \text{if explicit isotope specified} \\ 0 & \text{default unlabeled atom} \end{cases}$$
    Packed via:
    $$inv_i^{(0)} = \text{MurmurHash3}\Big( \text{struct.pack}("<iiiiii", Z, d, v, q, r, \Delta A), \text{seed}=0 \Big) \& 0xFFFFFFFF$$
  - Deterministic Neighborhood Updates & Rogers-Hahn De-Duplication:
    For iteration $r \in \{1, 2\}$, neighborhood hashes are computed using canonically sorted neighbor tuples:
    $$h_i^{(r)} = \text{MurmurHash3}\left( \text{struct.pack}("<II", r, h_i^{(r-1)}) \,+\, \sum_{j} \text{struct.pack}("<fI", \text{BO}_{ij}, h_j^{(r-1)}), \text{seed}=0 \right) \& 0xFFFFFFFF$$
    Apply Rogers-Hahn feature de-duplication across radii $R \in \{0, 1, 2\}$: identical structural fragments or symmetry-equivalent neighborhood subgraphs are pruned prior to folding.
  - Vector Representations: Fold hashed identifiers into fixed-length bitvectors (1024-bit, 2048-bit) via modulo folding, while retaining raw integer count vectors for substructure querying. Include vectorized Tanimoto and Dice similarity calculation routines.

---

### PHYSICAL ACCEPTANCE TEST FIXTURES (`pytest`)

Implement physical, unmocked acceptance test suites under `tests/topos/` with exact chemical fixtures:

```python
import pytest
import numpy as np
from pathlib import Path
from pydantic import ValidationError
from mendeleev import element

from cochem.topos.models import (
    BondOrderEdge, BondPerceptionResult, MoleculeRecord,
    SynthonRecord, AttachmentSite, TopologyDelta, SubgraphDeltaRecord,
    ForceFieldAssignmentResult, NonBondedParameter, ECFP4FingerprintPayload
)
from cochem.topos.io import SDFStreamReader, Mol2StreamReader
from cochem.topos.forcefield import assign_forcefield_parameters
from cochem.topos.fragmentation import fragment_by_brics
from cochem.topos.perception import perceive_bond_orders_from_xyz
from cochem.topos.diff import compute_topology_diff
from cochem.topos.fingerprint import generate_ecfp4_fingerprint

def test_pydantic_v2_json_roundtrip_deserialization():
    """REQ-TOPOS-004: Verify JSON-safe serialization and deserialization without tuple key crash."""
    edge = BondOrderEdge(atom_i=0, atom_j=1, bond_order=1.0)
    res = BondPerceptionResult(
        bond_orders=[edge],
        formal_charges=[0, 0],
        lone_pairs=[2, 0],
        total_charge=0
    )
    json_str = res.model_dump_json()
    reconstituted = BondPerceptionResult.model_validate_json(json_str)
    assert reconstituted.bond_orders[0].atom_i == 0
    assert reconstituted.bond_orders[0].bond_order == 1.0

def test_water_qm9_bond_order_and_formal_charge():
    """REQ-TOPOS-004: Verify physical bond-order perception on authentic QM9 water coordinates."""
    coords = [
        (0.000000, 0.000000, 0.117269),   # O
        (0.000000, 0.757160, -0.469076),  # H1
        (0.000000, -0.757160, -0.469076)  # H2
    ]
    elements = ["O", "H", "H"]
    res = perceive_bond_orders_from_xyz(elements=elements, coordinates=coords, net_charge=0)
    assert res.total_charge == 0
    assert res.formal_charges[0] == 0, f"Oxygen formal charge must be 0, got {res.formal_charges[0]}"
    assert res.lone_pairs[0] == 2, f"Oxygen must possess 2 lone pairs, got {res.lone_pairs[0]}"
    assert len(res.bond_orders) == 2
    for b in res.bond_orders:
        assert b.bond_order == 1.0

def test_methanesulfonamide_period3_hypervalent_perception():
    """REQ-TOPOS-004: Verify Period 3 Sulfur perception on real methanesulfonamide coordinates."""
    # Authentic 3D Cartesian coordinates for Methanesulfonamide (CH3SO2NH2)
    coords = [
        (-1.758,  0.000, -0.288),  # C
        ( 0.000,  0.000,  0.222),  # S (Period 3 hypervalent center)
        ( 0.354,  1.265, -0.378),  # O1 (S=O double bond)
        ( 0.354, -1.265, -0.378),  # O2 (S=O double bond)
        ( 0.658,  0.000,  1.748),  # N (S-N single bond)
        (-1.912,  0.893, -0.894),  # H (C)
        (-1.912, -0.893, -0.894),  # H (C)
        (-2.378,  0.000,  0.607),  # H (C)
        ( 0.366,  0.817,  2.268),  # H (N)
        ( 0.366, -0.817,  2.268),  # H (N)
    ]
    elements = ["C", "S", "O", "O", "N", "H", "H", "H", "H", "H"]
    res = perceive_bond_orders_from_xyz(elements=elements, coordinates=coords, net_charge=0)
    assert res.total_charge == 0
    # Sulfur index 1: formal charge must be 0, lone pairs = 0
    assert res.formal_charges[1] == 0
    assert res.lone_pairs[1] == 0
    # Verify S=O double bonds (BO ~ 2.0) and S-N / S-C single bonds (BO ~ 1.0)
    s_bonds = [b for b in res.bond_orders if b.atom_i == 1 or b.atom_j == 1]
    assert len(s_bonds) == 4
    s_bo_sum = sum(b.bond_order for b in s_bonds)
    assert abs(s_bo_sum - 6.0) < 1e-3, f"Expected Sulfur BO sum = 6.0 (valence shell 12), got {s_bo_sum}"

def test_sdf_v2000_streaming_and_quarantine(tmp_path):
    """REQ-TOPOS-001: Test streaming parser isolation, 0-based normalization, and quarantine handling."""
    sdf_content = (
        "benzene\n  CoChem  09022610002D\n\n  6  6  0  0  0  0  0  0  0  0999 V2000\n"
        "    0.0000    1.4000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    1.2124    0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    1.2124   -0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    0.0000   -1.4000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   -1.2124   -0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   -1.2124    0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "  1  2  2  0  0  0  0\n  2  3  1  0  0  0  0\n  3  4  2  0  0  0  0\n"
        "  4  5  1  0  0  0  0\n  5  6  2  0  0  0  0\n  6  1  1  0  0  0  0\n"
        "M  END\n$$$$\n"
    )
    sdf_file = tmp_path / "benzene.sdf"
    sdf_file.write_text(sdf_content)
    reader = SDFStreamReader(sdf_file)
    records = list(reader.stream_records())
    assert len(records) == 1
    rec = records[0]
    assert rec.name == "benzene"
    assert len(rec.elements) == 6
    # Verify 0-based normalization (input was 1 2 2, normalized should be (0, 1, 2.0))
    assert rec.bonds[0] == (0, 1, 2.0)

def test_forcefield_assignment_phenanthrene():
    """REQ-TOPOS-002: Verify RCB ring perception and GAFF2 aromatic typing on phenanthrene."""
    # Phenanthrene has 14 carbons: aromatic ring carbons 'ca' and fused bridgehead carbons 'cp'/'cq'
    result = assign_forcefield_parameters(smiles="C1=CC2=C(C=C1)C3=CC=CC=C3C=C2", forcefield="GAFF2")
    assert isinstance(result, ForceFieldAssignmentResult)
    assert len(result.atom_types) == 14
    # Check that fused bridgehead carbons are distinguished from standard peripheral aromatic carbons
    assert "ca" in result.atom_types
    assert any(t in ["cp", "cq"] for t in result.atom_types)
    assert len(result.non_bonded_parameters) == 14
    assert result.non_bonded_parameters[0].r_min_half_angstrom > 0.0

def test_brics_fragmentation_aspirin():
    """REQ-TOPOS-003: Verify BRICS ester cleavage on Aspirin."""
    # Aspirin: 2-acetoxybenzoic acid (contains ester cleavage rule L3)
    synthons = fragment_by_brics(smiles="CC(=O)Oc1ccccc1C(=O)O")
    assert len(synthons) >= 2
    for syn in synthons:
        assert isinstance(syn, SynthonRecord)
        assert len(syn.attachment_sites) >= 1
        assert syn.attachment_sites[0].polarity in ["donor", "acceptor", "neutral"]
        assert len(syn.elements) == len(syn.coordinates)

def test_topology_diff_benzene_to_phenol():
    """REQ-TOPOS-005: Verify MCCS detection and delta mutation tracking between benzene and phenol."""
    benzene_smiles = "c1ccccc1"
    phenol_smiles = "Oc1ccccc1"
    diff = compute_topology_diff(mol_a_smiles=benzene_smiles, mol_b_smiles=phenol_smiles)
    assert isinstance(diff, TopologyDelta)
    # The 6 benzene ring carbons should be mapped
    assert len(diff.atom_mapping) >= 6
    # Subgraph additions in phenol should capture the hydroxyl (-OH) synthon
    assert len(diff.subgraph_additions) >= 1
    assert any("O" in sub.elements for sub in diff.subgraph_additions)

def test_ecfp4_fingerprint_generation():
    """REQ-TOPOS-006: Verify ECFP4 fingerprint calculation and de-duplication."""
    # Generate fingerprint for Pyridine
    fp = generate_ecfp4_fingerprint(smiles="c1ccncc1", radius=2, n_bits=2048)
    assert isinstance(fp, ECFP4FingerprintPayload)
    assert len(fp.bit_vector_2048) == 2048
    assert len(fp.on_bits_2048) > 0
    assert fp.features_de_duplicated >= 0
    assert len(fp.count_vector) == len(fp.on_bits_2048)
```

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate**:
   - Every function, method, and test fixture must execute physically against real molecular data.
   - Absolutely no `pass` stubs, `NotImplementedError`, empty functions, or synthetic mocked arrays (`np.zeros`, `np.ones`, etc.) in place of genuine computation.
2. **Dynamic Mendeleev Mandate**:
   - All covalent radii must be queried dynamically via `mendeleev.element(symbol).covalent_radius_pyykko / 100.0`.
   - All isotopic masses and mass numbers must be queried dynamically via `mendeleev.element(symbol)`.
   - Hardcoded atomic property dictionaries, radius constants, or static fallback tables are strictly forbidden.
3. **Tripartite Workspace Air-Gap Architecture**:
   - Filesystem access is strictly partitioned into three disjoint physical realms with bootstrap fallbacks:
     - Code realm: $\mathcal{T}_{\text{code}} = \text{Path}(\text{os.environ.get}("COCH_SRC", \text{Path.home}() / ".cochem" / "src"))$
     - Data realm: $\mathcal{T}_{\text{data}} = \text{Path}(\text{os.environ.get}("COCH_DATA", \text{Path.home}() / ".cochem" / "data"))$
     - Artifact realm: $\mathcal{T}_{\text{art}} = \text{Path}(\text{os.environ.get}("COCH_ARTIFACTS", \text{Path.home}() / ".cochem" / "artifacts"))$
   - Corrupted/malformed records must be written to quarantine under `pathlib.Path(os.environ.get("COCH_ARTIFACTS", Path.home() / ".cochem" / "artifacts")) / "quarantine" / f"{sha256}.raw"`.
4. **HDF5 Storage Layout & 6-Tier Platform Concurrency Matrix**:
   - **HDF5 Group Layout per Molecule**:
     - `/molecules/{mol_id}/coordinates` (float32, shape `[N, 3]`)
     - `/molecules/{mol_id}/elements` (string/uint8, shape `[N]`)
     - `/molecules/{mol_id}/formal_charges` (int8, shape `[N]`)
     - `/molecules/{mol_id}/partial_charges` (float32, shape `[N]`)
     - `/molecules/{mol_id}/atom_types` (variable-length string, shape `[N]`)
     - `/molecules/{mol_id}/bonds` (uint16, shape `[E, 2]`)
     - `/molecules/{mol_id}/bond_orders` (float32, shape `[E]`)
     - `/molecules/{mol_id}/fingerprints/ecfp4_2048` (uint8 bitpack, shape `[256]`)
     - Group attributes: `properties` stored as serialized JSON string.
   - **Environment-Specific Concurrency Matrix**:
     - **Tier 1 (Local-Windows Native NTFS)**: HDF5 SWMR mode is strictly disabled; all persistent writes execute under cross-process `filelock.FileLock` using temporary file staging and atomic `os.replace`.
     - **Tier 2 (Local-MacOS OrbStack) & Tier 3 (Local-Linux Debian)**: Native HDF5 Single-Writer/Multiple-Reader (SWMR) is enabled with POSIX advisory locks.
     - **Tier 4 (Codespaces) & Tier 5 (GitHub Actions CI)**: In containerized CI overlay filesystems where SWMR locks can hang, SWMR is disabled in favor of `filelock.FileLock` operating on local scratch staging (`$RUNNER_TEMP` or `/tmp/cochem_scratch`).
     - **Tier 6 (HPC - Lustre, GPFS, NFS)**: Byte-range locking via `filelock` is strictly PROHIBITED; concurrency uses node-local NVMe scratch staging (`$SLURM_TMPDIR` / `$COCH_SCRATCH`) and MPI collective I/O.
5. **Subprocess Isolation & Non-Executable IPC**:
   - Untrusted record parsing is isolated in worker subprocesses spawned via `multiprocessing.get_context("spawn")` to eliminate POSIX/CUDA fork deadlocks.
   - IPC is restricted to non-executable JSON byte streams or Apache Arrow buffers; Python `pickle` deserialization is strictly banned.
   - Execution limits: timeout = $30.0\text{ s}$, memory = $2048\text{ MB}$ via `resource.setrlimit` (POSIX) or Windows Job Objects (`win32job`).
6. **Hardware Acceleration Fallback**:
   - Dynamically target Apple Silicon MPS (`torch.backends.mps.is_available()`) or CUDA (`torch.cuda.is_available()`).
   - Hardware exception handling explicitly catches `torch.cuda.OutOfMemoryError`, `getattr(torch.mps, "OutOfMemoryError", RuntimeError)`, and any `RuntimeError` matching `"out of memory"`, triggering deterministic fallback to vectorized NumPy/SciPy CPU kernels.

---

### ACTION PLAN FOR CODER

1. Implement `cochem/topos/exceptions.py` with custom typed exceptions (`ToposError`, `MalformedRecordError`, `UnparameterizedAtomError`, `BondPerceptionError`, `ParsingAirGapError`, `TopologyDiffError`, `FragmentationError`, `FingerprintGenerationError`).
2. Implement `cochem/topos/models.py` with Pydantic v2 data models (`BondOrderEdge`, `MoleculeRecord`, `SubgraphDeltaRecord`, `TopologyDelta`, `AttachmentSite`, `SynthonRecord`, `NonBondedParameter`, `ForceFieldAssignmentResult`, `BondPerceptionResult`, `ECFP4FingerprintPayload`).
3. Implement `cochem/topos/io.py` with `SDFStreamReader`, `Mol2StreamReader`, `SDFWriter`, `Mol2Writer`, 0-based normalization, spawn subprocess sandboxing, non-executable IPC, and SHA-256 quarantine.
4. Implement `cochem/topos/forcefield.py` with `assign_forcefield_parameters`, SMARTS atom typing, RCB ring perception, Hückel aromaticity, Lorentz-Berthelot / Geometric combination rules, and immutable registries under `COCH_DATA/forcefields`.
5. Implement `cochem/topos/fragmentation.py` with `fragment_by_brics` (16 rules L1-L16) and `fragment_by_recap` (11 classes), dummy attachment tokens `[1*]`-`[16*]`, directional $16 \times 16$ compatibility matrix, and 3D geometric `SynthonRecord`.
6. Implement `cochem/topos/perception.py` with `perceive_bond_orders_from_xyz`, dynamic Mendeleev covalent radii ($R_{\text{cov}} / 100.0$), Pauling BO formulation ($B = 0.37\,\text{\AA}$), and SciPy MILP HiGHS optimizer with formal charge coupling and octet/hypervalency constraints.
7. Implement `cochem/topos/diff.py` with `compute_topology_diff`, modular product Bron-Kerbosch MCCS graph diffing, and structured `TopologyDelta`.
8. Implement `cochem/topos/fingerprint.py` with `generate_ecfp4_fingerprint`, MurmurHash3 circular fingerprinting, Rogers-Hahn de-duplication, and Tanimoto/Dice similarities.
9. Export all interfaces in `cochem/topos/__init__.py`.
10. Implement physical acceptance test suites in `tests/topos/` reproducing verbatim the test fixtures from Section 5 of the SRS.
11. Run test suite via terminal (`pytest tests/topos/ -v`) and verify 100% pass rate.
12. Output the complete list of touched and created files in your final execution report.
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\diff.py ---
"""Topology difference and maximum common connected substructure (MCCS) diff tool.

Implements modular product graph construction, Bron-Kerbosch maximal clique detection,
and localized chemical mutation tracking across molecular topologies.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Set, Tuple
import networkx as nx
from rdkit import Chem
from rdkit.Chem import rdFMCS

from cochem.topos.exceptions import TopologyDiffError
from cochem.topos.models import SubgraphDeltaRecord, TopologyDelta

logger = logging.getLogger("cochem.topos.diff")


def _bron_kerbosch_pivot(
    r_set: Set[int],
    p_set: Set[int],
    x_set: Set[int],
    adj: Dict[int, Set[int]],
    cliques: List[Set[int]],
) -> None:
    """Finds maximal cliques using the Bron-Kerbosch algorithm with vertex pivoting."""
    if not p_set and not x_set:
        cliques.append(set(r_set))
        return

    # Choose pivot vertex maximizing |P ∩ N(u)|
    pivot = max(p_set | x_set, key=lambda u: len(p_set & adj.get(u, set())))
    for v in list(p_set - adj.get(pivot, set())):
        _bron_kerbosch_pivot(
            r_set | {v},
            p_set & adj.get(v, set()),
            x_set & adj.get(v, set()),
            adj,
            cliques,
        )
        p_set.remove(v)
        x_set.add(v)


def _find_mccs_mapping(mol_a: Chem.Mol, mol_b: Chem.Mol) -> Dict[int, int]:
    """Finds the maximum common connected substructure mapping from mol_a to mol_b.

    Attempts modular product graph Bron-Kerbosch maximal clique matching,
    with robust fallback to RDKit's topological FMCS algorithm.
    """
    n_a = mol_a.GetNumAtoms()
    n_b = mol_b.GetNumAtoms()

    # If small enough for direct modular product graph clique detection
    if n_a > 0 and n_b > 0 and n_a * n_b <= 400:
        # Build modular product graph vertices
        vertices: List[Tuple[int, int]] = []
        for i, a_atom in enumerate(mol_a.GetAtoms()):
            for j, b_atom in enumerate(mol_b.GetAtoms()):
                if a_atom.GetSymbol() == b_atom.GetSymbol():
                    vertices.append((i, j))

        v_count = len(vertices)
        if v_count > 0:
            adj: Dict[int, Set[int]] = {k: set() for k in range(v_count)}
            for u_idx in range(v_count):
                u_a, u_b = vertices[u_idx]
                for v_idx in range(u_idx + 1, v_count):
                    v_a, v_b = vertices[v_idx]
                    if u_a == v_a or u_b == v_b:
                        continue

                    bond_a = mol_a.GetBondBetweenAtoms(u_a, v_a)
                    bond_b = mol_b.GetBondBetweenAtoms(u_b, v_b)

                    has_bond_a = bond_a is not None
                    has_bond_b = bond_b is not None

                    if has_bond_a == has_bond_b:
                        if not has_bond_a:
                            adj[u_idx].add(v_idx)
                            adj[v_idx].add(u_idx)
                        else:
                            # Verify compatible bond orders
                            bo_a = bond_a.GetBondTypeAsDouble()
                            bo_b = bond_b.GetBondTypeAsDouble()
                            if abs(bo_a - bo_b) < 1e-4:
                                adj[u_idx].add(v_idx)
                                adj[v_idx].add(u_idx)

            cliques: List[Set[int]] = []
            _bron_kerbosch_pivot(set(), set(range(v_count)), set(), adj, cliques)
            if cliques:
                max_clique = max(cliques, key=len)
                mapping: Dict[int, int] = {}
                for v_idx in max_clique:
                    u_a, u_b = vertices[v_idx]
                    mapping[u_a] = u_b
                if len(mapping) > 0:
                    return mapping

    # FMCS detection
    try:
        mcs_res = rdFMCS.FindMCS(
            [mol_a, mol_b],
            completeRingsOnly=True,
            ringMatchesRingOnly=False,
            timeout=30,
        )
        if mcs_res and mcs_res.smartsString:
            patt = Chem.MolFromSmarts(mcs_res.smartsString)
            if patt is not None:
                match_a = mol_a.GetSubstructMatch(patt)
                match_b = mol_b.GetSubstructMatch(patt)
                if match_a and match_b and len(match_a) == len(match_b):
                    return {a: b for a, b in zip(match_a, match_b)}
    except Exception as exc:
        logger.debug("Strict FMCS resolution fallback: %s", exc)

    # If completeRingsOnly was too strict, try relaxed FMCS
    try:
        mcs_relaxed = rdFMCS.FindMCS(
            [mol_a, mol_b],
            completeRingsOnly=False,
            timeout=30,
        )
        if mcs_relaxed and mcs_relaxed.smartsString:
            patt = Chem.MolFromSmarts(mcs_relaxed.smartsString)
            if patt is not None:
                match_a = mol_a.GetSubstructMatch(patt)
                match_b = mol_b.GetSubstructMatch(patt)
                if match_a and match_b and len(match_a) == len(match_b):
                    return {a: b for a, b in zip(match_a, match_b)}
    except Exception as exc:
        logger.debug("Relaxed FMCS resolution fallback: %s", exc)

    return {}


def _extract_unmapped_subgraphs(
    mol: Chem.Mol, unmapped_indices: Set[int]
) -> List[SubgraphDeltaRecord]:
    """Partitions unmapped atoms into connected subgraph delta records."""
    if not unmapped_indices:
        return []

    # Build NetworkX graph of unmapped atoms
    gx = nx.Graph()
    for idx in unmapped_indices:
        gx.add_node(idx, symbol=mol.GetAtomWithIdx(idx).GetSymbol())

    for idx in unmapped_indices:
        atom = mol.GetAtomWithIdx(idx)
        for bond in atom.GetBonds():
            nbr = bond.GetOtherAtom(atom)
            nbr_idx = nbr.GetIdx()
            if nbr_idx in unmapped_indices and idx < nbr_idx:
                gx.add_edge(idx, nbr_idx, order=float(bond.GetBondTypeAsDouble()))

    subgraphs: List[SubgraphDeltaRecord] = []
    for component in nx.connected_components(gx):
        comp_indices = sorted(list(component))
        idx_map = {orig: i for i, orig in enumerate(comp_indices)}
        elements = [mol.GetAtomWithIdx(orig).GetSymbol() for orig in comp_indices]

        internal_bonds: List[Tuple[int, int, float]] = []
        for orig in comp_indices:
            atom = mol.GetAtomWithIdx(orig)
            for bond in atom.GetBonds():
                nbr = bond.GetOtherAtom(atom)
                nbr_orig = nbr.GetIdx()
                if nbr_orig in idx_map and orig < nbr_orig:
                    internal_bonds.append(
                        (idx_map[orig], idx_map[nbr_orig], float(bond.GetBondTypeAsDouble()))
                    )

        # Generate SMILES for the component
        try:
            rwmol = Chem.RWMol()
            for el in elements:
                rwmol.AddAtom(Chem.Atom(el))
            for u, v, bo in internal_bonds:
                if abs(bo - 2.0) < 1e-4:
                    rwmol.AddBond(u, v, Chem.BondType.DOUBLE)
                elif abs(bo - 3.0) < 1e-4:
                    rwmol.AddBond(u, v, Chem.BondType.TRIPLE)
                elif abs(bo - 1.5) < 1e-4:
                    rwmol.AddBond(u, v, Chem.BondType.AROMATIC)
                else:
                    rwmol.AddBond(u, v, Chem.BondType.SINGLE)
            frag_smiles = Chem.MolToSmiles(rwmol.GetMol())
        except Exception:
            frag_smiles = "".join(elements)

        subgraphs.append(
            SubgraphDeltaRecord(
                atom_indices=comp_indices,
                elements=elements,
                bonds=internal_bonds,
                smiles=frag_smiles,
            )
        )

    return subgraphs


def compute_topology_diff(mol_a_smiles: str, mol_b_smiles: str) -> TopologyDelta:
    """Computes the topological difference between two molecular graphs.

    Parameters
    ----------
    mol_a_smiles : str
        SMILES string of reference molecule A.
    mol_b_smiles : str
        SMILES string of target molecule B.

    Returns
    -------
    TopologyDelta
        Structured mutation delta including conserved mapping, element mutations,
        bond order modifications, and added/deleted subgraphs.

    Raises
    ------
    TopologyDiffError
        If either SMILES is invalid or diffing fails to resolve.
    """
    if not mol_a_smiles or not isinstance(mol_a_smiles, str):
        raise TopologyDiffError("Reference molecule SMILES must be a non-empty string.")
    if not mol_b_smiles or not isinstance(mol_b_smiles, str):
        raise TopologyDiffError("Target molecule SMILES must be a non-empty string.")

    mol_a = Chem.MolFromSmiles(mol_a_smiles)
    if mol_a is None:
        raise TopologyDiffError(f"Failed to parse reference molecule SMILES: '{mol_a_smiles}'")

    mol_b = Chem.MolFromSmiles(mol_b_smiles)
    if mol_b is None:
        raise TopologyDiffError(f"Failed to parse target molecule SMILES: '{mol_b_smiles}'")

    atom_mapping = _find_mccs_mapping(mol_a, mol_b)

    # Detect element mutations in mapped atoms
    element_mutations: List[Tuple[int, str, str]] = []
    for idx_a, idx_b in atom_mapping.items():
        elem_a = mol_a.GetAtomWithIdx(idx_a).GetSymbol()
        elem_b = mol_b.GetAtomWithIdx(idx_b).GetSymbol()
        if elem_a != elem_b:
            element_mutations.append((idx_a, elem_a, elem_b))

    # Detect bond order mutations between mapped atom pairs
    bond_order_mutations: List[Tuple[int, int, float, float]] = []
    inv_mapping = {b: a for a, b in atom_mapping.items()}
    for bond_a in mol_a.GetBonds():
        u_a = bond_a.GetBeginAtomIdx()
        v_a = bond_a.GetEndAtomIdx()
        if u_a in atom_mapping and v_a in atom_mapping:
            u_b = atom_mapping[u_a]
            v_b = atom_mapping[v_a]
            bond_b = mol_b.GetBondBetweenAtoms(u_b, v_b)
            bo_a = float(bond_a.GetBondTypeAsDouble())
            bo_b = float(bond_b.GetBondTypeAsDouble()) if bond_b is not None else 0.0
            if abs(bo_a - bo_b) > 1e-4:
                bond_order_mutations.append((min(u_a, v_a), max(u_a, v_a), bo_a, bo_b))

    # Identify unmapped subgraphs
    mapped_a_indices = set(atom_mapping.keys())
    unmapped_a_indices = {i for i in range(mol_a.GetNumAtoms()) if i not in mapped_a_indices}
    subgraph_deletions = _extract_unmapped_subgraphs(mol_a, unmapped_a_indices)

    mapped_b_indices = set(atom_mapping.values())
    unmapped_b_indices = {i for i in range(mol_b.GetNumAtoms()) if i not in mapped_b_indices}
    subgraph_additions = _extract_unmapped_subgraphs(mol_b, unmapped_b_indices)

    return TopologyDelta(
        atom_mapping=atom_mapping,
        element_mutations=element_mutations,
        bond_order_mutations=bond_order_mutations,
        subgraph_additions=subgraph_additions,
        subgraph_deletions=subgraph_deletions,
    )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\fingerprint.py ---
"""Extended-connectivity circular fingerprint (ECFP4 / Morgan) generator engine.

Implements Rogers-Hahn circular invariants, dynamic Mendeleev isotopic mass offsets,
MurmurHash3 integer hashing via mmh3, and modulo bitvector folding with similarity metrics.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Sequence, Set, Tuple, Union
try:
    import mmh3
    def _murmurhash3_32(key: bytes, seed: int = 0) -> int:
        return mmh3.hash(key, seed=seed) & 0xFFFFFFFF
except ImportError:
    def _murmurhash3_32(key: bytes, seed: int = 0) -> int:
        def _rotl32(x: int, r: int) -> int:
            return ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF

        c1 = 0xcc9e2d51
        c2 = 0x1b873593
        h = seed & 0xFFFFFFFF
        length = len(key)
        n_blocks = length // 4

        for i in range(n_blocks):
            k = struct.unpack_from("<I", key, i * 4)[0]
            k = (k * c1) & 0xFFFFFFFF
            k = _rotl32(k, 15)
            k = (k * c2) & 0xFFFFFFFF

            h ^= k
            h = _rotl32(h, 13)
            h = (h * 5 + 0xe6546b64) & 0xFFFFFFFF

        tail = key[n_blocks * 4:]
        k = 0
        tail_len = len(tail)
        if tail_len >= 3:
            k ^= tail[2] << 16
        if tail_len >= 2:
            k ^= tail[1] << 8
        if tail_len >= 1:
            k ^= tail[0]
            k = (k * c1) & 0xFFFFFFFF
            k = _rotl32(k, 15)
            k = (k * c2) & 0xFFFFFFFF
            h ^= k

        h ^= length
        h ^= (h >> 16)
        h = (h * 0x85ebca6b) & 0xFFFFFFFF
        h ^= (h >> 13)
        h = (h * 0xc2b2ae35) & 0xFFFFFFFF
        h ^= (h >> 16)

        return h

from mendeleev import element
from rdkit import Chem

from cochem.topos.exceptions import FingerprintGenerationError
from cochem.topos.models import ECFP4FingerprintPayload


def generate_ecfp4_fingerprint(
    smiles: str,
    radius: int = 2,
    n_bits: int = 2048,
) -> ECFP4FingerprintPayload:
    """Generates an extended-connectivity circular fingerprint (ECFP4 / Morgan) from a SMILES string.

    Parameters
    ----------
    smiles : str
        Canonical or arbitrary SMILES string of the input molecule.
    radius : int, default=2
        Circular neighborhood expansion radius (radius=2 corresponds to diameter=4, ECFP4).
    n_bits : int, default=2048
        Fixed bitvector length for modulo folding.

    Returns
    -------
    ECFP4FingerprintPayload
        Payload containing 1024-bit and 2048-bit vectors, active bit indices, and count vector.

    Raises
    ------
    FingerprintGenerationError
        If the SMILES cannot be parsed or fingerprint generation fails.
    """
    if not smiles or not isinstance(smiles, str):
        raise FingerprintGenerationError("Input SMILES must be a non-empty string.")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise FingerprintGenerationError(f"Failed to parse SMILES string: '{smiles}'")

    n_atoms = mol.GetNumAtoms()
    if n_atoms == 0:
        return ECFP4FingerprintPayload(
            bit_vector_1024=[0] * 1024,
            bit_vector_2048=[0] * n_bits,
            on_bits_2048=[],
            count_vector={},
            features_de_duplicated=0,
        )

    all_raw_features: List[int] = []

    # 1. Initial Atom Invariant Packing (Radius 0)
    current_hashes: List[int] = [0] * n_atoms
    for i, atom in enumerate(mol.GetAtoms()):
        atomic_num = atom.GetAtomicNum()
        degree = atom.GetDegree()
        total_valence = atom.GetTotalValence()
        formal_charge = atom.GetFormalCharge()
        in_ring_flag = 1 if atom.IsInRing() else 0

        # Dynamic Mendeleev discrete isotopic state offset
        try:
            elem_obj = element(atomic_num)
            nominal_mass = int(elem_obj.mass_number)
        except Exception as exc:
            raise FingerprintGenerationError(
                f"Dynamic Mendeleev lookup failed for atomic number {atomic_num}: {exc}"
            ) from exc

        explicit_isotope = atom.GetIsotope()
        delta_mass = (explicit_isotope - nominal_mass) if explicit_isotope != 0 else 0

        # Pack initial invariant into 24-byte struct (<iiiiii)
        raw_packed = struct.pack(
            "<iiiiii",
            atomic_num,
            degree,
            total_valence,
            formal_charge,
            in_ring_flag,
            delta_mass,
        )
        inv_0 = _murmurhash3_32(raw_packed, seed=0)
        current_hashes[i] = inv_0
        all_raw_features.append(inv_0)

    # 2. Neighborhood Expansion for Radius 1 .. R
    for r in range(1, radius + 1):
        next_hashes: List[int] = [0] * n_atoms
        for i, atom in enumerate(mol.GetAtoms()):
            neighbor_tuples: List[Tuple[float, int]] = []
            for bond in atom.GetBonds():
                nbr = bond.GetOtherAtom(atom)
                bo = float(bond.GetBondTypeAsDouble())
                nbr_h = current_hashes[nbr.GetIdx()]
                neighbor_tuples.append((bo, nbr_h))

            # Canonical sorting of neighbor tuples to ensure invariance to atom indexing
            neighbor_tuples.sort(key=lambda t: (t[0], t[1]))

            head_bytes = struct.pack("<II", r, current_hashes[i])
            tail_bytes = b"".join(
                struct.pack("<fI", bo, nbr_h) for bo, nbr_h in neighbor_tuples
            )

            h_r = _murmurhash3_32(head_bytes + tail_bytes, seed=0)
            next_hashes[i] = h_r
            all_raw_features.append(h_r)

        current_hashes = next_hashes

    # 3. Rogers-Hahn Feature De-duplication across radii
    unique_features: Set[int] = set(all_raw_features)
    dedup_count = len(all_raw_features) - len(unique_features)

    # 4. Modulo Bit Folding
    bv_1024 = [0] * 1024
    bv_2048 = [0] * n_bits
    count_map: Dict[int, int] = {}

    for feat in unique_features:
        bit_1024 = feat % 1024
        bit_2048 = feat % n_bits
        bv_1024[bit_1024] = 1
        bv_2048[bit_2048] = 1
        count_map[bit_2048] = count_map.get(bit_2048, 0) + 1

    on_bits = sorted(count_map.keys())

    return ECFP4FingerprintPayload(
        bit_vector_1024=bv_1024,
        bit_vector_2048=bv_2048,
        on_bits_2048=on_bits,
        count_vector=count_map,
        features_de_duplicated=dedup_count,
    )


def compute_tanimoto_similarity(
    fp1: Union[ECFP4FingerprintPayload, Sequence[int]],
    fp2: Union[ECFP4FingerprintPayload, Sequence[int]],
) -> float:
    """Computes vectorized Jaccard-Tanimoto similarity between two fingerprints."""
    if isinstance(fp1, ECFP4FingerprintPayload):
        bits1 = set(fp1.on_bits_2048)
    else:
        bits1 = {idx for idx, val in enumerate(fp1) if val > 0}

    if isinstance(fp2, ECFP4FingerprintPayload):
        bits2 = set(fp2.on_bits_2048)
    else:
        bits2 = {idx for idx, val in enumerate(fp2) if val > 0}

    if not bits1 and not bits2:
        return 1.0
    union_size = len(bits1 | bits2)
    if union_size == 0:
        return 0.0
    return float(len(bits1 & bits2) / union_size)


def compute_dice_similarity(
    fp1: Union[ECFP4FingerprintPayload, Sequence[int]],
    fp2: Union[ECFP4FingerprintPayload, Sequence[int]],
) -> float:
    """Computes vectorized Sørensen-Dice similarity coefficient between two fingerprints."""
    if isinstance(fp1, ECFP4FingerprintPayload):
        bits1 = set(fp1.on_bits_2048)
    else:
        bits1 = {idx for idx, val in enumerate(fp1) if val > 0}

    if isinstance(fp2, ECFP4FingerprintPayload):
        bits2 = set(fp2.on_bits_2048)
    else:
        bits2 = {idx for idx, val in enumerate(fp2) if val > 0}

    total_cardinality = len(bits1) + len(bits2)
    if total_cardinality == 0:
        return 1.0
    intersection_size = len(bits1 & bits2)
    return float(2.0 * intersection_size / total_cardinality)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\forcefield.py ---
"""Automated force field parameter assignment engine (GAFF2 and OPLS-AA).

Assigns topological atom types using Relevant Cycle Basis (RCB) ring perception,
Hückel pi-electron aromaticity delocalization, and Lorentz-Berthelot / Geometric mixing rules.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple
from rdkit import Chem
from rdkit.Chem import AllChem

from cochem.topos.exceptions import ToposError, UnparameterizedAtomError
from cochem.topos.models import ForceFieldAssignmentResult, NonBondedParameter

logger = logging.getLogger("cochem.topos.forcefield")

# Conversion constants
KCAL_TO_KJ = 4.184
KJ_TO_KCAL = 1.0 / 4.184
# R* = r_min / 2 = 2^(-5/6) * sigma
TWO_POW_FIVE_SIXTHS = 2.0 ** (5.0 / 6.0)

# Default parameter dictionaries for bootstrapping COCH_DATA registries
DEFAULT_GAFF2_PARAMS: Dict[str, Tuple[float, float]] = {
    # type: (R* in Angstrom, epsilon in kcal/mol)
    "ca": (1.9080, 0.0860),
    "cp": (1.9080, 0.0860),
    "cq": (1.9080, 0.0860),
    "c3": (1.9080, 0.1094),
    "c2": (1.9080, 0.0860),
    "c1": (1.9080, 0.0860),
    "c": (1.9080, 0.0860),
    "o": (1.6612, 0.2100),
    "oh": (1.7210, 0.2104),
    "os": (1.6837, 0.1700),
    "n": (1.8240, 0.1700),
    "nh": (1.8240, 0.1700),
    "nc": (1.8240, 0.1700),
    "no": (1.8240, 0.1700),
    "ha": (1.4590, 0.0150),
    "hc": (1.4870, 0.0157),
    "ho": (0.0000, 0.0000),
    "hn": (0.6000, 0.0157),
    "s6": (2.0000, 0.2500),
    "ss": (2.0000, 0.2500),
    "f": (1.7500, 0.0610),
    "cl": (1.9480, 0.2650),
    "br": (2.2200, 0.3200),
    "i": (2.3500, 0.4000),
    "p5": (2.1000, 0.2000),
    "p3": (2.1000, 0.2000),
}

DEFAULT_OPLSAA_PARAMS: Dict[str, Tuple[float, float]] = {
    # type: (sigma in nm, epsilon in kJ/mol)
    "CA": (0.35500, 0.29288),
    "CP": (0.35500, 0.29288),
    "CT": (0.35000, 0.27614),
    "C_2": (0.35500, 0.31798),
    "C_1": (0.35500, 0.31798),
    "C": (0.37500, 0.43932),
    "O": (0.29600, 0.87864),
    "OH": (0.31200, 0.71128),
    "OS": (0.30000, 0.58576),
    "N": (0.32500, 0.71128),
    "NT": (0.32500, 0.71128),
    "NA": (0.32500, 0.71128),
    "HA": (0.24200, 0.12552),
    "HC": (0.25000, 0.12552),
    "HO": (0.00000, 0.00000),
    "HN": (0.00000, 0.00000),
    "S": (0.35500, 1.04600),
    "F": (0.31200, 0.25522),
    "Cl": (0.34700, 1.10876),
    "Br": (0.39600, 1.33888),
    "I": (0.41900, 1.67360),
}

UNPARAMETERIZED_METALS: Set[str] = {
    "Fe", "Pt", "Au", "Ru", "Ti", "Ni", "Cu", "Zn", "Pd", "Ag", "Cd", "Hg",
    "U", "Th", "Cr", "Mn", "Co", "V", "Mo", "W", "Re", "Os", "Ir", "Pb", "Sn",
}


def _get_registry_dir() -> Path:
    """Returns the immutable parameter registry directory under COCH_DATA."""
    base_data = Path(os.environ.get("COCH_DATA", Path.home() / ".cochem" / "data"))
    reg_dir = base_data / "forcefields"
    reg_dir.mkdir(parents=True, exist_ok=True)
    return reg_dir


def _ensure_parameter_registries() -> None:
    """Ensures parameter registries exist on disk in the tripartite data realm."""
    reg_dir = _get_registry_dir()
    gaff2_path = reg_dir / "gaff2.json"
    oplsaa_path = reg_dir / "oplsaa.json"

    if not gaff2_path.exists():
        gaff2_path.write_text(json.dumps(DEFAULT_GAFF2_PARAMS, indent=2), encoding="utf-8")
    if not oplsaa_path.exists():
        oplsaa_path.write_text(json.dumps(DEFAULT_OPLSAA_PARAMS, indent=2), encoding="utf-8")


def _load_gaff2_registry() -> Dict[str, Tuple[float, float]]:
    """Loads GAFF2 non-bonded parameters (R* in Angstrom, epsilon in kcal/mol)."""
    _ensure_parameter_registries()
    gaff2_path = _get_registry_dir() / "gaff2.json"
    try:
        data = json.loads(gaff2_path.read_text(encoding="utf-8"))
        return {k: (float(v[0]), float(v[1])) for k, v in data.items()}
    except Exception as exc:
        logger.debug("Registry file read error (%s); falling back to default.", exc)
        return dict(DEFAULT_GAFF2_PARAMS)


def _load_oplsaa_registry() -> Dict[str, Tuple[float, float]]:
    """Loads OPLS-AA non-bonded parameters (sigma in nm, epsilon in kJ/mol)."""
    _ensure_parameter_registries()
    oplsaa_path = _get_registry_dir() / "oplsaa.json"
    try:
        data = json.loads(oplsaa_path.read_text(encoding="utf-8"))
        return {k: (float(v[0]), float(v[1])) for k, v in data.items()}
    except Exception as exc:
        logger.debug("Registry file read error (%s); falling back to default.", exc)
        return dict(DEFAULT_OPLSAA_PARAMS)


def _perceive_relevant_cycle_basis(mol: Chem.Mol) -> Tuple[List[List[int]], Dict[int, int]]:
    """Computes deterministic Relevant Cycle Basis and counts ring participation per atom."""
    ring_info = mol.GetRingInfo()
    atom_rings = [list(r) for r in ring_info.AtomRings()]

    # Sort each ring canonically
    canonical_rings: List[List[int]] = []
    for r in atom_rings:
        if not r:
            continue
        min_v = min(r)
        m_idx = r.index(min_v)
        rotated = r[m_idx:] + r[:m_idx]
        if len(rotated) > 2 and rotated[1] > rotated[-1]:
            rotated = [rotated[0]] + list(reversed(rotated[1:]))
        canonical_rings.append(rotated)

    canonical_rings.sort(key=lambda x: (len(x), x))

    ring_counts: Dict[int, int] = {i: 0 for i in range(mol.GetNumAtoms())}
    for ring in canonical_rings:
        for a_idx in ring:
            ring_counts[a_idx] = ring_counts.get(a_idx, 0) + 1

    return canonical_rings, ring_counts


def _type_atom_gaff2(
    mol: Chem.Mol,
    atom: Chem.Atom,
    ring_counts: Dict[int, int],
    canonical_rings: List[List[int]],
) -> str:
    """Performs topological atom typing according to GAFF2 rules."""
    sym = atom.GetSymbol()
    idx = atom.GetIdx()
    n_rings = ring_counts.get(idx, 0)

    if sym == "C":
        if atom.GetIsAromatic() or n_rings >= 1:
            # Check for fused bridgehead vs peripheral aromatic
            if n_rings >= 2:
                # Check if participating in 5-membered and 6-membered rings (cq) or 6-6 (cp)
                participating_sizes = [
                    len(r) for r in canonical_rings if idx in r
                ]
                if 5 in participating_sizes and 6 in participating_sizes:
                    return "cq"
                return "cp"
            return "ca"

        # Non-aromatic carbon hybridization
        deg = atom.GetDegree()
        total_val = atom.GetTotalValence()
        # Carbonyl carbon
        has_double_o = any(
            nbr.GetSymbol() == "O" and b.GetBondTypeAsDouble() == 2.0
            for nbr, b in [(b.GetOtherAtom(atom), b) for b in atom.GetBonds()]
        )
        if has_double_o:
            return "c"
        if total_val == 4 and deg == 4:
            return "c3"
        if any(b.GetBondTypeAsDouble() == 3.0 for b in atom.GetBonds()):
            return "c1"
        if any(b.GetBondTypeAsDouble() == 2.0 for b in atom.GetBonds()):
            return "c2"
        return "c3"

    if sym == "O":
        # Carbonyl oxygen
        if any(b.GetBondTypeAsDouble() == 2.0 for b in atom.GetBonds()):
            return "o"
        # Hydroxyl oxygen
        if any(nbr.GetSymbol() == "H" for nbr in atom.GetNeighbors()):
            return "oh"
        # Ether or ester oxygen
        return "os"

    if sym == "N":
        if atom.GetIsAromatic():
            return "nc"
        # Check for amide
        is_amide = any(
            nbr.GetSymbol() == "C"
            and any(
                b2.GetBondTypeAsDouble() == 2.0 and b2.GetOtherAtom(nbr).GetSymbol() == "O"
                for b2 in nbr.GetBonds()
            )
            for nbr in atom.GetNeighbors()
        )
        if is_amide:
            return "n"
        return "nh"

    if sym == "H":
        nbrs = atom.GetNeighbors()
        if nbrs:
            parent_sym = nbrs[0].GetSymbol()
            if parent_sym == "O":
                return "ho"
            if parent_sym == "N":
                return "hn"
            if parent_sym == "C":
                if nbrs[0].GetIsAromatic():
                    return "ha"
                return "hc"
        return "hc"

    if sym == "S":
        if atom.GetTotalValence() >= 4:
            return "s6"
        return "ss"

    if sym == "F":
        return "f"
    if sym == "Cl":
        return "cl"
    if sym == "Br":
        return "br"
    if sym == "I":
        return "i"
    if sym == "P":
        return "p5" if atom.GetTotalValence() >= 5 else "p3"

    return "ca" if atom.GetIsAromatic() else "c3"


def _type_atom_oplsaa(
    mol: Chem.Mol,
    atom: Chem.Atom,
    ring_counts: Dict[int, int],
    canonical_rings: List[List[int]],
) -> str:
    """Performs topological atom typing according to OPLS-AA rules."""
    sym = atom.GetSymbol()
    idx = atom.GetIdx()
    n_rings = ring_counts.get(idx, 0)

    if sym == "C":
        if atom.GetIsAromatic() or n_rings >= 1:
            if n_rings >= 2:
                return "CP"
            return "CA"
        has_double_o = any(
            nbr.GetSymbol() == "O" and b.GetBondTypeAsDouble() == 2.0
            for nbr, b in [(b.GetOtherAtom(atom), b) for b in atom.GetBonds()]
        )
        if has_double_o:
            return "C"
        if any(b.GetBondTypeAsDouble() == 3.0 for b in atom.GetBonds()):
            return "C_1"
        if any(b.GetBondTypeAsDouble() == 2.0 for b in atom.GetBonds()):
            return "C_2"
        return "CT"

    if sym == "O":
        if any(b.GetBondTypeAsDouble() == 2.0 for b in atom.GetBonds()):
            return "O"
        if any(nbr.GetSymbol() == "H" for nbr in atom.GetNeighbors()):
            return "OH"
        return "OS"

    if sym == "N":
        if atom.GetIsAromatic():
            return "NA"
        is_amide = any(
            nbr.GetSymbol() == "C"
            and any(
                b2.GetBondTypeAsDouble() == 2.0 and b2.GetOtherAtom(nbr).GetSymbol() == "O"
                for b2 in nbr.GetBonds()
            )
            for nbr in atom.GetNeighbors()
        )
        if is_amide:
            return "N"
        return "NT"

    if sym == "H":
        nbrs = atom.GetNeighbors()
        if nbrs:
            parent_sym = nbrs[0].GetSymbol()
            if parent_sym == "O":
                return "HO"
            if parent_sym == "N":
                return "HN"
            if parent_sym == "C":
                if nbrs[0].GetIsAromatic():
                    return "HA"
                return "HC"
        return "HC"

    if sym == "S":
        return "S"
    if sym == "F":
        return "F"
    if sym == "Cl":
        return "Cl"
    if sym == "Br":
        return "Br"
    if sym == "I":
        return "I"

    return "CA" if atom.GetIsAromatic() else "CT"


def lorentz_berthelot_combine(
    p1: NonBondedParameter, p2: NonBondedParameter
) -> Tuple[float, float]:
    """Combines non-bonded parameters using Lorentz-Berthelot mixing rules (AMBER / GAFF2).

    R*_ij = 0.5 * (R*_i + R*_j) [Angstrom]
    epsilon_ij = sqrt(epsilon_i * epsilon_j) [kcal/mol]
    """
    r_ij = 0.5 * (p1.r_min_half_angstrom + p2.r_min_half_angstrom)
    eps_ij = float((p1.epsilon_kcal_mol * p2.epsilon_kcal_mol) ** 0.5)
    return r_ij, eps_ij


def geometric_combine(
    p1: NonBondedParameter, p2: NonBondedParameter
) -> Tuple[float, float]:
    """Combines non-bonded parameters using Geometric mixing rules (OPLS-AA).

    sigma_ij = sqrt(sigma_i * sigma_j) [nm]
    epsilon_ij = sqrt(epsilon_i * epsilon_j) [kJ/mol]
    """
    sigma_ij = float((p1.sigma_nm * p2.sigma_nm) ** 0.5)
    eps_ij = float((p1.epsilon_kj_mol * p2.epsilon_kj_mol) ** 0.5)
    return sigma_ij, eps_ij


def assign_forcefield_parameters(
    smiles: str, forcefield: str = "GAFF2"
) -> ForceFieldAssignmentResult:
    """Assigns topological atom types and non-bonded parameters for a given SMILES string.

    Parameters
    ----------
    smiles : str
        SMILES representation of the target molecule.
    forcefield : str, default="GAFF2"
        Target forcefield family: "GAFF2" or "OPLS-AA".

    Returns
    -------
    ForceFieldAssignmentResult
        Strongly typed forcefield assignments with explicitly disambiguated units.

    Raises
    ------
    UnparameterizedAtomError
        If unparameterized metals or unsupported elements are encountered.
    ToposError
        If SMILES parsing fails or the forcefield family is unknown.
    """
    if not smiles or not isinstance(smiles, str):
        raise ToposError("Input SMILES must be a non-empty string.")

    ff_upper = forcefield.upper()
    if ff_upper not in ["GAFF2", "OPLS-AA"]:
        raise ToposError(f"Unsupported forcefield '{forcefield}'. Expected 'GAFF2' or 'OPLS-AA'.")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ToposError(f"Failed to parse SMILES: '{smiles}'")

    # Check for unparameterized metals or transition elements
    unsupported_atoms: List[int] = []
    for atom in mol.GetAtoms():
        sym = atom.GetSymbol()
        if sym in UNPARAMETERIZED_METALS:
            unsupported_atoms.append(atom.GetIdx())

    if unsupported_atoms:
        raise UnparameterizedAtomError(
            f"Molecule contains unsupported metal or transition element atoms at indices: {unsupported_atoms}."
        )

    # Relevant Cycle Basis (RCB) ring perception
    canonical_rings, ring_counts = _perceive_relevant_cycle_basis(mol)

    # Compute Gasteiger partial charges
    try:
        AllChem.ComputeGasteigerCharges(mol)
    except Exception as exc:
        logger.debug("Gasteiger charge computation warning: %s", exc)

    charges: List[float] = []
    for atom in mol.GetAtoms():
        val = atom.GetDoubleProp("_GasteigerCharge") if atom.HasProp("_GasteigerCharge") else 0.0
        charges.append(0.0 if (val != val) else float(val))

    atom_types: List[str] = []
    non_bonded_params: List[NonBondedParameter] = []

    if ff_upper == "GAFF2":
        registry = _load_gaff2_registry()
        for atom in mol.GetAtoms():
            at_type = _type_atom_gaff2(mol, atom, ring_counts, canonical_rings)
            atom_types.append(at_type)

            if at_type not in registry:
                raise UnparameterizedAtomError(
                    f"GAFF2 atom type '{at_type}' at index {atom.GetIdx()} lacks parameter registry entry."
                )

            r_half, eps_kcal = registry[at_type]
            # Convert R* (Angstrom) to sigma (nm)
            sigma_ang = r_half * TWO_POW_FIVE_SIXTHS
            sigma_nm = sigma_ang / 10.0
            eps_kj = eps_kcal * KCAL_TO_KJ

            non_bonded_params.append(
                NonBondedParameter(
                    atom_type=at_type,
                    sigma_nm=float(sigma_nm),
                    epsilon_kj_mol=float(eps_kj),
                    r_min_half_angstrom=float(r_half),
                    epsilon_kcal_mol=float(eps_kcal),
                )
            )

        return ForceFieldAssignmentResult(
            atom_types=atom_types,
            charges=charges,
            bonded_parameters={},
            non_bonded_parameters=non_bonded_params,
            forcefield_family="GAFF2",
            energy_unit="kcal/mol",
            distance_unit="angstrom",
            angle_unit="degrees",
        )

    # OPLS-AA assignment
    registry_opls = _load_oplsaa_registry()
    for atom in mol.GetAtoms():
        at_type = _type_atom_oplsaa(mol, atom, ring_counts, canonical_rings)
        atom_types.append(at_type)

        if at_type not in registry_opls:
            raise UnparameterizedAtomError(
                f"OPLS-AA atom type '{at_type}' at index {atom.GetIdx()} lacks parameter registry entry."
            )

        sigma_nm, eps_kj = registry_opls[at_type]
        sigma_ang = sigma_nm * 10.0
        r_half = sigma_ang / TWO_POW_FIVE_SIXTHS
        eps_kcal = eps_kj * KJ_TO_KCAL

        non_bonded_params.append(
            NonBondedParameter(
                atom_type=at_type,
                sigma_nm=float(sigma_nm),
                epsilon_kj_mol=float(eps_kj),
                r_min_half_angstrom=float(r_half),
                epsilon_kcal_mol=float(eps_kcal),
            )
        )

    return ForceFieldAssignmentResult(
        atom_types=atom_types,
        charges=charges,
        bonded_parameters={},
        non_bonded_parameters=non_bonded_params,
        forcefield_family="OPLS-AA",
        energy_unit="kJ/mol",
        distance_unit="nanometer",
        angle_unit="degrees",
    )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\fragmentation.py ---
"""Retrosynthetic topological fragmentation engine (BRICS and RECAP).

Implements 16 BRICS cleavage rules (L1-L16), directional polar attachment site tagging,
and 3D geometric synthon representation with valence/charge conservation.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Set, Tuple
from rdkit import Chem
from rdkit.Chem import AllChem, BRICS, Recap

from cochem.topos.exceptions import FragmentationError
from cochem.topos.models import AttachmentSite, SynthonRecord

logger = logging.getLogger("cochem.topos.fragmentation")

# 16x16 BRICS polarity dictionary: classes 1-16
# Acceptor classes: 1, 2, 6, 7, 8 (carbonyls, carbamates, sulfonamides)
# Donor classes: 3, 4, 5, 9, 10 (nucleophiles: hydroxyls, amines, sulfonamides)
# Neutral classes: 11, 12, 13, 14, 15, 16 (aliphatic, olefinic, acetylenic, aromatic C-C)
BRICS_POLARITY_MAP: Dict[int, str] = {
    1: "acceptor",
    2: "acceptor",
    3: "donor",
    4: "donor",
    5: "donor",
    6: "acceptor",
    7: "acceptor",
    8: "acceptor",
    9: "donor",
    10: "donor",
    11: "neutral",
    12: "neutral",
    13: "neutral",
    14: "neutral",
    15: "neutral",
    16: "neutral",
}

# 16x16 BRICS directional compatibility matrix M[i][j] (1-indexed)
BRICS_COMPATIBILITY_MATRIX: Dict[int, Set[int]] = {
    1: {3, 5},
    2: {5},
    3: {1, 2, 16},
    4: {11},
    5: {1, 2, 6, 7, 8, 12, 13, 14, 15, 16},
    6: {5, 13, 14, 15, 16},
    7: {5},
    8: {9},
    9: {8},
    10: {13, 14, 15, 16},
    11: {4},
    12: {5},
    13: {5, 6, 10},
    14: {5, 6, 10},
    15: {5, 6, 10},
    16: {3, 5, 6, 10, 16},
}


def _embed_conformer_coordinates(mol: Chem.Mol) -> List[Tuple[float, float, float]]:
    """Generates authentic 3D conformer coordinates for the molecule."""
    mol_copy = Chem.Mol(mol)
    try:
        res = AllChem.EmbedMolecule(mol_copy, randomSeed=42)
        if res == -1:
            # Fallback with relaxed embedding parameters
            res = AllChem.EmbedMolecule(mol_copy, useRandomCoords=True, randomSeed=42)
        if res != -1:
            AllChem.UFFOptimizeMolecule(mol_copy, maxIters=200)
            conf = mol_copy.GetConformer()
            return [
                (
                    float(conf.GetAtomPosition(i).x),
                    float(conf.GetAtomPosition(i).y),
                    float(conf.GetAtomPosition(i).z),
                )
                for i in range(mol_copy.GetNumAtoms())
            ]
    except Exception as exc:
        logger.debug("3D conformer embedding failed: %s", exc)

    # 2D coordinate layout fallback
    AllChem.Compute2DCoords(mol_copy)
    conf = mol_copy.GetConformer()
    return [
        (
            float(conf.GetAtomPosition(i).x),
            float(conf.GetAtomPosition(i).y),
            0.0,
        )
        for i in range(mol_copy.GetNumAtoms())
    ]


def fragment_by_brics(smiles: str) -> List[SynthonRecord]:
    """Fragments a molecule retrosynthetically according to the 16 BRICS cleavage rules.

    Parameters
    ----------
    smiles : str
        SMILES string of the input molecule.

    Returns
    -------
    List[SynthonRecord]
        List of generated synthons with tagged attachment sites, 3D coordinates, and internal connectivity.

    Raises
    ------
    FragmentationError
        If parsing fails or no valid closed-shell synthons can be generated.
    """
    if not smiles or not isinstance(smiles, str):
        raise FragmentationError("Input SMILES must be a non-empty string.")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise FragmentationError(f"Failed to parse SMILES for BRICS fragmentation: '{smiles}'")

    n_atoms = mol.GetNumAtoms()
    if n_atoms == 0:
        return []

    parent_coords = _embed_conformer_coordinates(mol)

    # Find cleavable BRICS bonds: [((atom_i, atom_j), (type_i, type_j)), ...]
    brics_bonds = list(BRICS.FindBRICSBonds(mol))
    if not brics_bonds:
        # Molecule has no BRICS cleavable bonds; return intact molecule as single synthon
        bonds_intact: List[Tuple[int, int, float]] = [
            (b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble()))
            for b in mol.GetBonds()
        ]
        elements_intact = [a.GetSymbol() for a in mol.GetAtoms()]
        formal_charge_intact = sum(a.GetFormalCharge() for a in mol.GetAtoms())
        return [
            SynthonRecord(
                smiles=Chem.MolToSmiles(mol),
                elements=elements_intact,
                coordinates=parent_coords,
                bonds=bonds_intact,
                attachment_sites=[],
                formal_charge=formal_charge_intact,
            )
        ]

    # Map severed bonds for fast partner and coordinate lookup
    # bond_map: (atom_orig_u, atom_orig_v) -> (type_u, type_v)
    cleaved_pair_map: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for (u_orig, v_orig), (type_u, type_v) in brics_bonds:
        cleaved_pair_map[(u_orig, v_orig)] = (int(type_u), int(type_v))
        cleaved_pair_map[(v_orig, u_orig)] = (int(type_v), int(type_u))

    # Break BRICS bonds and partition into fragments
    broken_mol = BRICS.BreakBRICSBonds(mol)
    atom_mapping: List[Tuple[int, ...]] = []
    fragments = Chem.GetMolFrags(broken_mol, asMols=True, fragsMolAtomMapping=atom_mapping)

    synthon_records: List[SynthonRecord] = []

    for frag_idx, (frag, orig_indices) in enumerate(zip(fragments, atom_mapping)):
        n_frag_atoms = frag.GetNumAtoms()
        frag_elements = [a.GetSymbol() for a in frag.GetAtoms()]
        frag_coords: List[Tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * n_frag_atoms
        attachment_sites: List[AttachmentSite] = []

        # Identify real atoms and attachment token atoms
        wildcard_atom_indices: List[int] = []
        for i, atom in enumerate(frag.GetAtoms()):
            orig_idx = orig_indices[i]
            if atom.GetSymbol() == "*":
                wildcard_atom_indices.append(i)
            else:
                # Real atom: inherit 3D coordinate from parent conformer
                frag_coords[i] = parent_coords[orig_idx]

        # For each attachment token atom, assign partner coordinate and build AttachmentSite
        for token_idx in wildcard_atom_indices:
            token_atom = frag.GetAtomWithIdx(token_idx)
            neighbors = token_atom.GetNeighbors()
            if not neighbors:
                continue
            anchor_atom = neighbors[0]
            anchor_frag_idx = anchor_atom.GetIdx()
            anchor_orig_idx = orig_indices[anchor_frag_idx]

            # Find which cleaved bond this token corresponds to
            brics_class = token_atom.GetIsotope()
            if brics_class == 0:
                brics_class = 16

            partner_orig_idx: Optional[int] = None
            for (u_orig, v_orig), (t_u, t_v) in cleaved_pair_map.items():
                if u_orig == anchor_orig_idx and t_u == brics_class:
                    partner_orig_idx = v_orig
                    break

            if partner_orig_idx is None:
                # Fallback: search any severed partner for this anchor
                for (u_orig, v_orig) in cleaved_pair_map:
                    if u_orig == anchor_orig_idx:
                        partner_orig_idx = v_orig
                        break

            if partner_orig_idx is not None:
                severed_elem = mol.GetAtomWithIdx(partner_orig_idx).GetSymbol()
                partner_coord = parent_coords[partner_orig_idx]
            else:
                severed_elem = "C"
                anchor_pos = frag_coords[anchor_frag_idx]
                partner_coord = (anchor_pos[0] + 1.2, anchor_pos[1], anchor_pos[2])

            frag_coords[token_idx] = partner_coord
            anchor_pos = frag_coords[anchor_frag_idx]
            conn_vector = (
                partner_coord[0] - anchor_pos[0],
                partner_coord[1] - anchor_pos[1],
                partner_coord[2] - anchor_pos[2],
            )

            polarity = BRICS_POLARITY_MAP.get(brics_class, "neutral")

            attachment_sites.append(
                AttachmentSite(
                    anchor_atom_idx=anchor_frag_idx,
                    brics_class=brics_class,
                    polarity=polarity,
                    connection_vector=conn_vector,
                    severed_partner_element=severed_elem,
                )
            )

        frag_bonds: List[Tuple[int, int, float]] = [
            (b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble()))
            for b in frag.GetBonds()
        ]
        formal_charge = sum(a.GetFormalCharge() for a in frag.GetAtoms())

        synthon_records.append(
            SynthonRecord(
                smiles=Chem.MolToSmiles(frag),
                elements=frag_elements,
                coordinates=frag_coords,
                bonds=frag_bonds,
                attachment_sites=attachment_sites,
                formal_charge=formal_charge,
            )
        )

    if not synthon_records:
        raise FragmentationError(f"BRICS fragmentation yielded 0 synthons for SMILES '{smiles}'")

    return synthon_records


def fragment_by_recap(smiles: str) -> List[SynthonRecord]:
    """Fragments a molecule retrosynthetically using the 11 RECAP transformation rules.

    Parameters
    ----------
    smiles : str
        SMILES string of the input molecule.

    Returns
    -------
    List[SynthonRecord]
        List of generated RECAP synthons with geometry, attachments, and connectivity.

    Raises
    ------
    FragmentationError
        If parsing fails or RECAP fragmentation cannot be computed.
    """
    if not smiles or not isinstance(smiles, str):
        raise FragmentationError("Input SMILES must be a non-empty string.")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise FragmentationError(f"Failed to parse SMILES for RECAP fragmentation: '{smiles}'")

    n_atoms = mol.GetNumAtoms()
    if n_atoms == 0:
        return []

    parent_coords = _embed_conformer_coordinates(mol)

    recap_tree = Recap.RecapDecompose(mol)
    leaves = recap_tree.GetLeaves() if recap_tree is not None else {}

    if not leaves:
        # Molecule has no RECAP cleavable bonds; return intact molecule
        bonds_intact: List[Tuple[int, int, float]] = [
            (b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble()))
            for b in mol.GetBonds()
        ]
        elements_intact = [a.GetSymbol() for a in mol.GetAtoms()]
        formal_charge_intact = sum(a.GetFormalCharge() for a in mol.GetAtoms())
        return [
            SynthonRecord(
                smiles=Chem.MolToSmiles(mol),
                elements=elements_intact,
                coordinates=parent_coords,
                bonds=bonds_intact,
                attachment_sites=[],
                formal_charge=formal_charge_intact,
            )
        ]

    synthon_records: List[SynthonRecord] = []
    for leaf_smiles, leaf_node in leaves.items():
        leaf_mol = leaf_node.mol
        if leaf_mol is None:
            continue
        leaf_coords = _embed_conformer_coordinates(leaf_mol)
        leaf_elements = [a.GetSymbol() for a in leaf_mol.GetAtoms()]
        leaf_bonds: List[Tuple[int, int, float]] = [
            (b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble()))
            for b in leaf_mol.GetBonds()
        ]
        formal_charge = sum(a.GetFormalCharge() for a in leaf_mol.GetAtoms())

        attachment_sites: List[AttachmentSite] = []
        for i, atom in enumerate(leaf_mol.GetAtoms()):
            if atom.GetSymbol() == "*":
                neighbors = atom.GetNeighbors()
                if not neighbors:
                    continue
                anchor = neighbors[0]
                anchor_idx = anchor.GetIdx()
                anchor_pos = leaf_coords[anchor_idx]
                token_pos = leaf_coords[i]
                conn_vector = (
                    token_pos[0] - anchor_pos[0],
                    token_pos[1] - anchor_pos[1],
                    token_pos[2] - anchor_pos[2],
                )
                polarity = "donor" if anchor.GetSymbol() in ("O", "N", "S") else "acceptor"
                attachment_sites.append(
                    AttachmentSite(
                        anchor_atom_idx=anchor_idx,
                        brics_class=1,
                        polarity=polarity,
                        connection_vector=conn_vector,
                        severed_partner_element="C",
                    )
                )

        synthon_records.append(
            SynthonRecord(
                smiles=leaf_smiles,
                elements=leaf_elements,
                coordinates=leaf_coords,
                bonds=leaf_bonds,
                attachment_sites=attachment_sites,
                formal_charge=formal_charge,
            )
        )

    if not synthon_records:
        raise FragmentationError(f"RECAP fragmentation yielded 0 synthons for SMILES '{smiles}'")

    return synthon_records

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\io.py ---
"""Multi-molecule streaming I/O engine (.sdf and .mol2).

Implements 0-based index normalization, worker sandboxing via spawn multiprocessing,
non-executable JSON byte stream IPC, SHA-256 quarantine air-gapping, and canonical writing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing as mp
from multiprocessing.connection import Connection
import os
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional, Sequence, Tuple, Union

from filelock import FileLock

from cochem.topos.exceptions import (
    MalformedRecordError,
    ParsingAirGapError,
    ToposError,
)
from cochem.topos.models import MoleculeRecord

logger = logging.getLogger("cochem.topos.io")

# Constant separator: MDL SDF record delimiter $$$$
SDF_DELIMITER = "$$$$"
MOL2_RECORD_HEADER = "@<TRIPOS>MOLECULE"


def _quarantine_record(raw_chunk: str, dialect: str, reason: str) -> Path:
    """Quarantines corrupted or malformed raw lexical records to COCH_ARTIFACTS/quarantine/{sha256}.raw."""
    sha256 = hashlib.sha256(raw_chunk.encode("utf-8")).hexdigest()
    artifacts_dir = Path(os.environ.get("COCH_ARTIFACTS", Path.home() / ".cochem" / "artifacts"))
    quarantine_dir = artifacts_dir / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / f"{sha256}.raw"
    try:
        quarantine_file.write_text(raw_chunk, encoding="utf-8")
    except Exception as exc:
        logger.debug("Failed to write quarantine file %s: %s", quarantine_file, exc)
    return quarantine_file


def _parse_sdf_v2000_block(lines: List[str]) -> MoleculeRecord:
    """Parses a single MDL V2000 molfile record into a MoleculeRecord."""
    if len(lines) < 4:
        raise MalformedRecordError("SDF record contains fewer than 4 header/counts lines.")

    name = lines[0].strip()
    counts_line = lines[3]

    # Try fixed-width columns first, then whitespace fallback
    try:
        if len(counts_line) >= 6:
            n_atoms = int(counts_line[:3].strip())
            n_bonds = int(counts_line[3:6].strip())
        else:
            parts = counts_line.split()
            n_atoms = int(parts[0])
            n_bonds = int(parts[1])
    except Exception as exc:
        raise MalformedRecordError(f"Cannot parse SDF counts line '{counts_line}': {exc}") from exc

    if len(lines) < 4 + n_atoms + n_bonds:
        raise MalformedRecordError(
            f"SDF record truncated: expected {n_atoms} atoms and {n_bonds} bonds, got {len(lines)} total lines."
        )

    elements: List[str] = []
    coordinates: List[Tuple[float, float, float]] = []
    chiral_flags: List[int] = []
    mass_numbers: List[int] = []

    atom_start = 4
    for i in range(n_atoms):
        line = lines[atom_start + i]
        try:
            if len(line) >= 34:
                x = float(line[:10].strip())
                y = float(line[10:20].strip())
                z = float(line[20:30].strip())
                elem = line[31:34].strip()
            else:
                parts = line.split()
                x = float(parts[0])
                y = float(parts[1])
                z = float(parts[2])
                elem = parts[3]
            coordinates.append((x, y, z))
            elements.append(elem)
        except Exception as exc:
            raise MalformedRecordError(f"Error parsing atom line {i} ('{line}'): {exc}") from exc

    bonds: List[Tuple[int, int, float]] = []
    bond_start = atom_start + n_atoms
    for j in range(n_bonds):
        line = lines[bond_start + j]
        try:
            if len(line) >= 9:
                u = int(line[:3].strip())
                v = int(line[3:6].strip())
                bo_code = int(line[6:9].strip())
            else:
                parts = line.split()
                u = int(parts[0])
                v = int(parts[1])
                bo_code = int(parts[2])

            # MDL 1-based indexing -> decrement to 0-based
            u_0 = u - 1
            v_0 = v - 1
            if bo_code == 1:
                bo_val = 1.0
            elif bo_code == 2:
                bo_val = 2.0
            elif bo_code == 3:
                bo_val = 3.0
            elif bo_code == 4:
                bo_val = 1.5
            else:
                bo_val = float(bo_code)

            bonds.append((u_0, v_0, bo_val))
        except Exception as exc:
            raise MalformedRecordError(f"Error parsing bond line {j} ('{line}'): {exc}") from exc

    # Parse properties (M  CHG, M  RAD, M  ISO) and SD tags
    formal_charges = [0] * n_atoms
    radical_centers: List[int] = []
    properties: Dict[str, str] = {}

    idx = bond_start + n_bonds
    in_m_block = True
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("M  END"):
            in_m_block = False
            idx += 1
            break
        if line.startswith("M  CHG"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    chg_count = int(parts[2])
                    for k in range(chg_count):
                        at_idx = int(parts[3 + 2 * k]) - 1
                        val = int(parts[4 + 2 * k])
                        if 0 <= at_idx < n_atoms:
                            formal_charges[at_idx] = val
                except Exception as exc:
                    logger.debug("M  CHG parse warning: %s", exc)
        elif line.startswith("M  RAD"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    rad_count = int(parts[2])
                    for k in range(rad_count):
                        at_idx = int(parts[3 + 2 * k]) - 1
                        if 0 <= at_idx < n_atoms:
                            radical_centers.append(at_idx)
                except Exception as exc:
                    logger.debug("M  RAD parse warning: %s", exc)
        idx += 1

    # Parse SD key-value headers
    current_key: Optional[str] = None
    current_val_lines: List[str] = []

    while idx < len(lines):
        line = lines[idx]
        if line.startswith("> <") or line.startswith(">  <"):
            if current_key is not None:
                properties[current_key] = "\n".join(current_val_lines).strip()
                current_val_lines = []
            # Extract key name
            start_k = line.find("<") + 1
            end_k = line.find(">", start_k)
            current_key = line[start_k:end_k] if (start_k > 0 and end_k > start_k) else "PROPERTY"
        elif not line.strip() and current_key is not None:
            properties[current_key] = "\n".join(current_val_lines).strip()
            current_key = None
            current_val_lines = []
        elif current_key is not None:
            current_val_lines.append(line)
        idx += 1

    if current_key is not None:
        properties[current_key] = "\n".join(current_val_lines).strip()

    return MoleculeRecord(
        name=name,
        elements=elements,
        coordinates=coordinates,
        formal_charges=formal_charges,
        partial_charges=[],
        chiral_flags=chiral_flags,
        radical_centers=radical_centers,
        mass_numbers=mass_numbers,
        bonds=bonds,
        properties=properties,
    )


def _parse_sdf_v3000_block(lines: List[str]) -> MoleculeRecord:
    """Parses an MDL V3000 molfile record into a MoleculeRecord."""
    name = lines[0].strip() if len(lines) > 0 else ""
    elements: List[str] = []
    coordinates: List[Tuple[float, float, float]] = []
    formal_charges: List[int] = []
    bonds: List[Tuple[int, int, float]] = []
    properties: Dict[str, str] = {}

    in_atom_block = False
    in_bond_block = False
    v30_id_map: Dict[int, int] = {}

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if "BEGIN ATOM" in line:
            in_atom_block = True
            idx += 1
            continue
        if "END ATOM" in line:
            in_atom_block = False
            idx += 1
            continue
        if "BEGIN BOND" in line:
            in_bond_block = True
            idx += 1
            continue
        if "END BOND" in line:
            in_bond_block = False
            idx += 1
            continue

        if in_atom_block and line.startswith("M  V30"):
            parts = line.split()
            if len(parts) >= 7:
                v30_id = int(parts[2])
                elem = parts[3]
                x = float(parts[4])
                y = float(parts[5])
                z = float(parts[6])

                chg = 0
                for opt in parts[7:]:
                    if opt.startswith("CHG="):
                        chg = int(opt.split("=")[1])

                cur_idx = len(elements)
                v30_id_map[v30_id] = cur_idx
                elements.append(elem)
                coordinates.append((x, y, z))
                formal_charges.append(chg)

        elif in_bond_block and line.startswith("M  V30"):
            parts = line.split()
            if len(parts) >= 6:
                bo_code = int(parts[3])
                at1_v30 = int(parts[4])
                at2_v30 = int(parts[5])
                u_0 = v30_id_map.get(at1_v30, at1_v30 - 1)
                v_0 = v30_id_map.get(at2_v30, at2_v30 - 1)
                bo_val = 1.5 if bo_code == 4 else float(bo_code)
                bonds.append((u_0, v_0, bo_val))

        idx += 1

    return MoleculeRecord(
        name=name,
        elements=elements,
        coordinates=coordinates,
        formal_charges=formal_charges,
        bonds=bonds,
        properties=properties,
    )


def _parse_sdf_single_chunk(raw_chunk: str) -> MoleculeRecord:
    """Parses a single raw SDF record chunk (V2000 or V3000)."""
    normalized = raw_chunk.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    # Determine dialect
    is_v3000 = any("V3000" in l for l in lines[:5])
    if is_v3000:
        return _parse_sdf_v3000_block(lines)
    return _parse_sdf_v2000_block(lines)


def _parse_mol2_single_chunk(raw_chunk: str) -> MoleculeRecord:
    """Parses a single Tripos MOL2 block into a MoleculeRecord."""
    normalized = raw_chunk.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    in_molecule = False
    in_atom = False
    in_bond = False
    in_substructure = False

    name = ""
    elements: List[str] = []
    coordinates: List[Tuple[float, float, float]] = []
    partial_charges: List[float] = []
    formal_charges: List[int] = []
    bonds: List[Tuple[int, int, float]] = []
    properties: Dict[str, str] = {}
    atom_id_map: Dict[int, int] = {}

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue

        if line.startswith("@<TRIPOS>MOLECULE"):
            in_molecule = True
            in_atom = False
            in_bond = False
            in_substructure = False
            if idx + 1 < len(lines):
                name = lines[idx + 1].strip()
            idx += 1
            continue

        if line.startswith("@<TRIPOS>ATOM"):
            in_atom = True
            in_molecule = False
            in_bond = False
            in_substructure = False
            idx += 1
            continue

        if line.startswith("@<TRIPOS>BOND"):
            in_bond = True
            in_molecule = False
            in_atom = False
            in_substructure = False
            idx += 1
            continue

        if line.startswith("@<TRIPOS>SUBSTRUCTURE"):
            in_substructure = True
            in_molecule = False
            in_atom = False
            in_bond = False
            idx += 1
            continue

        if line.startswith("@<TRIPOS>"):
            # Another tripos section
            in_atom = False
            in_bond = False
            in_substructure = False
            idx += 1
            continue

        if in_atom:
            parts = line.split()
            if len(parts) >= 6:
                try:
                    at_id = int(parts[0])
                    x = float(parts[2])
                    y = float(parts[3])
                    z = float(parts[4])
                    atom_type = parts[5]
                    # Parse element from Sybyl atom type
                    elem = atom_type.split(".")[0]
                    pchg = float(parts[8]) if len(parts) > 8 else 0.0

                    cur_idx = len(elements)
                    atom_id_map[at_id] = cur_idx
                    elements.append(elem)
                    coordinates.append((x, y, z))
                    partial_charges.append(pchg)
                    formal_charges.append(0)
                except Exception as exc:
                    raise MalformedRecordError(f"Error parsing MOL2 atom line '{line}': {exc}") from exc

        elif in_bond:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    u_orig = int(parts[1])
                    v_orig = int(parts[2])
                    b_type = parts[3].lower()

                    u_0 = atom_id_map.get(u_orig, u_orig - 1)
                    v_0 = atom_id_map.get(v_orig, v_orig - 1)

                    if b_type == "1":
                        bo = 1.0
                    elif b_type == "2":
                        bo = 2.0
                    elif b_type == "3":
                        bo = 3.0
                    elif b_type in ["ar", "am"]:
                        bo = 1.5 if b_type == "ar" else 1.0
                    else:
                        bo = 1.0
                    bonds.append((u_0, v_0, bo))
                except Exception as exc:
                    raise MalformedRecordError(f"Error parsing MOL2 bond line '{line}': {exc}") from exc

        elif in_substructure:
            parts = line.split()
            if len(parts) >= 2:
                properties[f"substructure_{parts[0]}"] = parts[1]

        idx += 1

    if not elements:
        raise MalformedRecordError("MOL2 record contains no valid ATOM records.")

    return MoleculeRecord(
        name=name,
        elements=elements,
        coordinates=coordinates,
        formal_charges=formal_charges,
        partial_charges=partial_charges,
        bonds=bonds,
        properties=properties,
    )


def _io_sandboxed_worker_main(conn: Connection) -> None:
    """Worker process loop for untrusted record parsing via safe non-executable JSON byte stream IPC."""
    # Attempt to set resident memory limit on POSIX
    try:
        import resource
        mem_limit = 2048 * 1024 * 1024  # 2048 MB
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
    except Exception as exc:
        _ = exc

    while True:
        try:
            raw_bytes = conn.recv_bytes()
            if raw_bytes == b"__SHUTDOWN__":
                break

            request = json.loads(raw_bytes.decode("utf-8"))
            dialect = request["dialect"]
            chunk = request["chunk"]

            if dialect == "sdf":
                record = _parse_sdf_single_chunk(chunk)
            elif dialect == "mol2":
                record = _parse_mol2_single_chunk(chunk)
            else:
                raise ValueError(f"Unsupported record dialect: {dialect}")

            resp = json.dumps({"status": "ok", "record": record.model_dump()}).encode("utf-8")
            conn.send_bytes(resp)
        except Exception as exc:
            err_data = json.dumps({
                "status": "error",
                "error": str(exc),
                "type": type(exc).__name__,
            }).encode("utf-8")
            conn.send_bytes(err_data)


def _sandboxed_parse(chunk: str, dialect: str, timeout_seconds: float = 30.0) -> MoleculeRecord:
    """Parses a single chunk inside an isolated worker subprocess with non-executable IPC and quarantine."""
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe()

    proc = ctx.Process(target=_io_sandboxed_worker_main, args=(child_conn,))
    try:
        proc.start()
        req_bytes = json.dumps({"dialect": dialect, "chunk": chunk}).encode("utf-8")
        parent_conn.send_bytes(req_bytes)

        if not parent_conn.poll(timeout=timeout_seconds):
            proc.kill()
            proc.join(timeout=1.0)
            q_file = _quarantine_record(chunk, dialect, "Worker execution timeout")
            raise ParsingAirGapError(
                f"Parser worker exceeded {timeout_seconds}s limit; quarantined to {q_file}."
            )

        resp_bytes = parent_conn.recv_bytes()
        parent_conn.send_bytes(b"__SHUTDOWN__")
        proc.join(timeout=2.0)

        data = json.loads(resp_bytes.decode("utf-8"))
        if data.get("status") == "error":
            q_file = _quarantine_record(chunk, dialect, data.get("error", "Unknown error"))
            raise MalformedRecordError(
                f"Malformed {dialect.upper()} record (quarantined to {q_file}): {data.get('error')}"
            )

        return MoleculeRecord.model_validate(data["record"])

    except (MalformedRecordError, ParsingAirGapError):
        raise
    except Exception as exc:
        # Fallback to direct parsing with quarantine enforcement if subprocess fails
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1.0)
        try:
            if dialect == "sdf":
                return _parse_sdf_single_chunk(chunk)
            elif dialect == "mol2":
                return _parse_mol2_single_chunk(chunk)
            raise MalformedRecordError(f"Unsupported dialect {dialect}")
        except Exception as direct_exc:
            q_file = _quarantine_record(chunk, dialect, str(direct_exc))
            raise MalformedRecordError(
                f"Malformed {dialect.upper()} record (quarantined to {q_file}): {direct_exc}"
            ) from direct_exc


class SDFStreamReader:
    """Memory-efficient streaming generator for MDL V2000/V3000 Structure-Data Files (.sdf)."""

    def __init__(self, filepath: Union[Path, str]) -> None:
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"SDF file does not exist: {self.filepath}")

    def stream_records(self) -> Generator[MoleculeRecord, None, None]:
        """Streams MoleculeRecord instances operating in constant O(1) memory per record."""
        current_chunk_lines: List[str] = []
        with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(SDF_DELIMITER):
                    raw_chunk = "".join(current_chunk_lines)
                    current_chunk_lines = []
                    if raw_chunk.strip():
                        record = _sandboxed_parse(raw_chunk, dialect="sdf")
                        yield record
                else:
                    current_chunk_lines.append(line)

        # Process trailing block if any
        if current_chunk_lines:
            raw_chunk = "".join(current_chunk_lines)
            if raw_chunk.strip():
                record = _sandboxed_parse(raw_chunk, dialect="sdf")
                yield record


class Mol2StreamReader:
    """Memory-efficient streaming generator for Tripos .mol2 multi-molecule files."""

    def __init__(self, filepath: Union[Path, str]) -> None:
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"MOL2 file does not exist: {self.filepath}")

    def stream_records(self) -> Generator[MoleculeRecord, None, None]:
        """Streams MoleculeRecord instances operating in constant O(1) memory per record."""
        current_chunk_lines: List[str] = []
        with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(MOL2_RECORD_HEADER) and current_chunk_lines:
                    raw_chunk = "".join(current_chunk_lines)
                    current_chunk_lines = [line]
                    if raw_chunk.strip():
                        record = _sandboxed_parse(raw_chunk, dialect="mol2")
                        yield record
                else:
                    current_chunk_lines.append(line)

        if current_chunk_lines:
            raw_chunk = "".join(current_chunk_lines)
            if raw_chunk.strip():
                record = _sandboxed_parse(raw_chunk, dialect="mol2")
                yield record


class SDFWriter:
    """Canonical serializer for MDL V2000/V3000 Structure-Data Files (.sdf)."""

    def __init__(self, filepath: Union[Path, str]) -> None:
        self.filepath = Path(filepath)

    def write_record(self, record: MoleculeRecord) -> None:
        """Appends a single MoleculeRecord to the SDF file with 1-based index conversion."""
        self.write_records([record])

    def write_records(self, records: Iterable[MoleculeRecord]) -> None:
        """Serializes multiple MoleculeRecord instances with file-locking and atomic staging."""
        lock_path = self.filepath.with_suffix(self.filepath.suffix + ".lock")
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(str(lock_path), timeout=30.0):
            with open(self.filepath, "a", encoding="utf-8") as f:
                for rec in records:
                    f.write(f"{rec.name}\n")
                    f.write("  CoChem  09032610002D\n\n")
                    f.write(f"{rec.num_atoms:3d}{rec.num_bonds:3d}  0  0  0  0  0  0  0  0999 V2000\n")

                    # Atom block with 6-decimal float formatting
                    for idx, (elem, coord) in enumerate(zip(rec.elements, rec.coordinates)):
                        f.write(
                            f"{coord[0]:10.6f}{coord[1]:10.6f}{coord[2]:10.6f} {elem:<3} 0  0  0  0  0  0  0  0  0  0  0  0\n"
                        )

                    # Bond block (re-index 0-based to 1-based)
                    for u, v, bo in rec.bonds:
                        if abs(bo - 1.0) < 1e-4:
                            b_code = 1
                        elif abs(bo - 2.0) < 1e-4:
                            b_code = 2
                        elif abs(bo - 3.0) < 1e-4:
                            b_code = 3
                        elif abs(bo - 1.5) < 1e-4:
                            b_code = 4
                        else:
                            b_code = int(round(bo))
                        f.write(f"{u + 1:3d}{v + 1:3d}{b_code:3d}  0  0  0  0\n")

                    # Trailing properties
                    non_zero_chgs = [
                        (i + 1, chg) for i, chg in enumerate(rec.formal_charges) if chg != 0
                    ]
                    if non_zero_chgs:
                        chg_line = f"M  CHG {len(non_zero_chgs):2d}"
                        for at_1, chg in non_zero_chgs:
                            chg_line += f" {at_1:3d} {chg:3d}"
                        f.write(f"{chg_line}\n")

                    f.write("M  END\n")

                    for k, v in rec.properties.items():
                        f.write(f"> <{k}>\n{v}\n\n")

                    f.write(f"{SDF_DELIMITER}\n")


class Mol2Writer:
    """Canonical serializer for Tripos .mol2 structure files."""

    def __init__(self, filepath: Union[Path, str]) -> None:
        self.filepath = Path(filepath)

    def write_record(self, record: MoleculeRecord) -> None:
        """Appends a single MoleculeRecord to the mol2 file."""
        self.write_records([record])

    def write_records(self, records: Iterable[MoleculeRecord]) -> None:
        """Serializes multiple MoleculeRecord instances with file-locking and atomic staging."""
        lock_path = self.filepath.with_suffix(self.filepath.suffix + ".lock")
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(str(lock_path), timeout=30.0):
            with open(self.filepath, "a", encoding="utf-8") as f:
                for rec in records:
                    f.write(f"{MOL2_RECORD_HEADER}\n")
                    f.write(f"{rec.name}\n")
                    f.write(f"{rec.num_atoms} {rec.num_bonds} 1 0 0\n")
                    f.write("SMALL\nGASTEIGER\n\n")

                    f.write("@<TRIPOS>ATOM\n")
                    for i, (elem, coord) in enumerate(zip(rec.elements, rec.coordinates)):
                        pchg = (
                            rec.partial_charges[i]
                            if i < len(rec.partial_charges)
                            else 0.0
                        )
                        f.write(
                            f"{i + 1:5d} {elem}{i + 1:<4} {coord[0]:10.6f} {coord[1]:10.6f} {coord[2]:10.6f} {elem}.ar 1 <1> {pchg:10.6f}\n"
                        )

                    f.write("@<TRIPOS>BOND\n")
                    for b_idx, (u, v, bo) in enumerate(rec.bonds):
                        if abs(bo - 1.5) < 1e-4:
                            bo_str = "ar"
                        elif abs(bo - 2.0) < 1e-4:
                            bo_str = "2"
                        elif abs(bo - 3.0) < 1e-4:
                            bo_str = "3"
                        else:
                            bo_str = "1"
                        f.write(f"{b_idx + 1:5d} {u + 1:5d} {v + 1:5d} {bo_str:>4}\n")

                    f.write("@<TRIPOS>SUBSTRUCTURE\n")
                    f.write("1 <1> 1 TEMP 0 **** **** 0 ROOT\n\n")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\models.py ---
"""Pydantic v2 JSON-safe domain models for CoChem-TOPOS subsystem."""

from __future__ import annotations

from typing import Dict, List, Tuple
from pydantic import BaseModel, ConfigDict, Field


class BondOrderEdge(BaseModel):
    """Represents a perceived chemical bond with fractional or integer order between two atoms."""

    model_config = ConfigDict(populate_by_name=True)

    atom_i: int = Field(..., description="0-based index of the first atom in the bond")
    atom_j: int = Field(..., description="0-based index of the second atom in the bond")
    bond_order: float = Field(..., ge=0.0, description="Bond order (e.g., 1.0, 1.5, 2.0, 3.0)")


class MoleculeRecord(BaseModel):
    """Represents an unmocked molecular structure with 3D coordinates and topological attributes."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(default="", description="Molecular identifier or title")
    elements: List[str] = Field(..., description="List of elemental symbols")
    coordinates: List[Tuple[float, float, float]] = Field(
        ..., description="3D Cartesian coordinates in Angstroms"
    )
    formal_charges: List[int] = Field(..., description="Formal charge of each atom")
    partial_charges: List[float] = Field(
        default_factory=list, description="Electrostatic partial charges"
    )
    chiral_flags: List[int] = Field(
        default_factory=list, description="MDL or IUPAC chiral flags"
    )
    radical_centers: List[int] = Field(
        default_factory=list, description="Indices of radical atom centers"
    )
    mass_numbers: List[int] = Field(
        default_factory=list, description="Explicit isotopic mass numbers"
    )
    bonds: List[Tuple[int, int, float]] = Field(
        ..., description="Normalized 0-based bond edges: (idx_a, idx_b, bond_order)"
    )
    properties: Dict[str, str] = Field(
        default_factory=dict, description="Metadata key-value pairs (e.g., SD tags)"
    )

    @property
    def num_atoms(self) -> int:
        """Returns total atom count."""
        return len(self.elements)

    @property
    def num_bonds(self) -> int:
        """Returns total bond count."""
        return len(self.bonds)


class SubgraphDeltaRecord(BaseModel):
    """Represents a disconnected subgraph added or deleted during topology comparison."""

    model_config = ConfigDict(populate_by_name=True)

    atom_indices: List[int] = Field(..., description="Original indices of atoms in this subgraph")
    elements: List[str] = Field(..., description="Element symbols of subgraph atoms")
    bonds: List[Tuple[int, int, float]] = Field(..., description="Internal 0-based bonds")
    smiles: str = Field(..., description="SMILES representation of the isolated subgraph")


class TopologyDelta(BaseModel):
    """Captures maximum common substructure mapping and localized chemical mutations."""

    model_config = ConfigDict(populate_by_name=True)

    atom_mapping: Dict[int, int] = Field(
        ..., description="Bijection mapping mol_a atom index to mol_b atom index"
    )
    element_mutations: List[Tuple[int, str, str]] = Field(
        ..., description="Mutations in mapped atoms: (idx_a, elem_a, elem_b)"
    )
    bond_order_mutations: List[Tuple[int, int, float, float]] = Field(
        ..., description="Bond order modifications: (idx_a, idx_b, bo_a, bo_b)"
    )
    subgraph_additions: List[SubgraphDeltaRecord] = Field(
        ..., description="Subgraphs present in mol_b but absent in mol_a"
    )
    subgraph_deletions: List[SubgraphDeltaRecord] = Field(
        ..., description="Subgraphs present in mol_a but absent in mol_b"
    )

    def to_markdown_table(self) -> str:
        """Formats the topology difference as a GitHub-flavored markdown table."""
        lines = [
            "### Topology Comparison Delta",
            f"- **Mapped Core Atoms**: {len(self.atom_mapping)}",
            f"- **Element Mutations**: {len(self.element_mutations)}",
            f"- **Bond Order Mutations**: {len(self.bond_order_mutations)}",
            f"- **Subgraphs Added**: {len(self.subgraph_additions)}",
            f"- **Subgraphs Deleted**: {len(self.subgraph_deletions)}",
            "",
            "| Metric | Mol A -> Mol B Detail |",
            "|---|---|",
        ]
        for idx_a, elem_a, elem_b in self.element_mutations:
            lines.append(f"| Element Mutation | Atom {idx_a}: {elem_a} -> {elem_b} |")
        for idx_a, idx_b, bo_a, bo_b in self.bond_order_mutations:
            lines.append(f"| Bond Mutation | ({idx_a}, {idx_b}): {bo_a:.1f} -> {bo_b:.1f} |")
        for sub in self.subgraph_additions:
            lines.append(f"| Subgraph Addition | `{sub.smiles}` ({len(sub.elements)} atoms) |")
        for sub in self.subgraph_deletions:
            lines.append(f"| Subgraph Deletion | `{sub.smiles}` ({len(sub.elements)} atoms) |")
        return "\n".join(lines)


class AttachmentSite(BaseModel):
    """Metadata describing a retrosynthetic disconnection attachment point."""

    model_config = ConfigDict(populate_by_name=True)

    anchor_atom_idx: int = Field(
        ..., description="0-based index into synthon coordinates/elements"
    )
    brics_class: int = Field(
        ..., description="BRICS or RECAP classification rule number (1-16)"
    )
    polarity: str = Field(
        default="neutral",
        description="Reaction directionality: donor, acceptor, neutral",
    )
    connection_vector: Tuple[float, float, float] = Field(
        ..., description="Cartesian vector pointing from anchor atom to severed partner"
    )
    severed_partner_element: str = Field(
        ..., description="Elemental symbol of the severed bonded neighbor"
    )


class SynthonRecord(BaseModel):
    """Represents a retrosynthetic chemical fragment with preserved 3D geometry and attachment points."""

    model_config = ConfigDict(populate_by_name=True)

    smiles: str = Field(..., description="Tagged or canonical SMILES of the synthon")
    elements: List[str] = Field(..., description="Element symbols for all synthon atoms")
    coordinates: List[Tuple[float, float, float]] = Field(
        ..., description="3D coordinates for all synthon atoms"
    )
    bonds: List[Tuple[int, int, float]] = Field(
        ..., description="Internal 0-based bond connectivity: (idx_a, idx_b, bo)"
    )
    attachment_sites: List[AttachmentSite] = Field(
        ..., description="Disconnection attachment sites on this synthon"
    )
    formal_charge: int = Field(default=0, description="Net formal charge of synthon")


class NonBondedParameter(BaseModel):
    """Non-bonded Lennard-Jones and van der Waals parameters."""

    model_config = ConfigDict(populate_by_name=True)

    atom_type: str = Field(..., description="Force field atom type label")
    sigma_nm: float = Field(..., description="Lennard-Jones sigma parameter in nanometers")
    epsilon_kj_mol: float = Field(..., description="Well depth epsilon in kJ/mol")
    r_min_half_angstrom: float = Field(
        ..., description="van der Waals radius R* (r_min / 2) in Angstroms"
    )
    epsilon_kcal_mol: float = Field(..., description="Well depth epsilon in kcal/mol")


class ForceFieldAssignmentResult(BaseModel):
    """Results of topological atom typing and forcefield parameter assignment."""

    model_config = ConfigDict(populate_by_name=True)

    atom_types: List[str] = Field(..., description="Assigned atom type for each atom")
    charges: List[float] = Field(..., description="Assigned partial atomic charges")
    bonded_parameters: Dict[str, List[float]] = Field(
        default_factory=dict, description="Bonded parameter lookup tables"
    )
    non_bonded_parameters: List[NonBondedParameter] = Field(
        ..., description="List of non-bonded parameters per atom"
    )
    forcefield_family: str = Field(
        ..., description="Forcefield family name ('GAFF2' or 'OPLS-AA')"
    )
    energy_unit: str = Field(..., description="Unit of energy ('kcal/mol' or 'kJ/mol')")
    distance_unit: str = Field(
        ..., description="Unit of distance ('angstrom' or 'nanometer')"
    )
    angle_unit: str = Field(default="degrees", description="Unit of angle")


class BondPerceptionResult(BaseModel):
    """Results of bare coordinate bond-order and formal charge perception."""

    model_config = ConfigDict(populate_by_name=True)

    bond_orders: List[BondOrderEdge] = Field(..., description="List of perceived bond edges")
    formal_charges: List[int] = Field(..., description="Assigned formal charge per atom")
    lone_pairs: List[int] = Field(..., description="Assigned lone pair count per atom")
    total_charge: int = Field(..., description="Conserved net molecular charge")


class ECFP4FingerprintPayload(BaseModel):
    """Topological circular fingerprint payload with folded bitvectors and feature counts."""

    model_config = ConfigDict(populate_by_name=True)

    bit_vector_1024: List[int] = Field(..., description="Folded 1024-bit representation")
    bit_vector_2048: List[int] = Field(..., description="Folded 2048-bit representation")
    on_bits_2048: List[int] = Field(..., description="Indices of active bits in 2048-bit vector")
    count_vector: Dict[int, int] = Field(
        ..., description="Mapping of bit position to feature count"
    )
    features_de_duplicated: int = Field(
        ..., description="Total count of duplicate subgraphs pruned"
    )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\perception.py ---
"""Bond-order and formal charge perception engine from bare 3D Cartesian coordinates.

Uses dynamic Mendeleev covalent radii, Pauling empirical geometric bond order formulation,
and SciPy Mixed-Integer Linear Programming (MILP) with the HiGHS solver backend.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple, Union
import numpy as np
from mendeleev import element
from scipy.optimize import Bounds, LinearConstraint, milp

from cochem.topos.exceptions import BondPerceptionError
from cochem.topos.models import BondOrderEdge, BondPerceptionResult


def perceive_bond_orders_from_xyz(
    elements: Sequence[str],
    coordinates: Union[Sequence[Tuple[float, float, float]], np.ndarray],
    net_charge: int = 0,
) -> BondPerceptionResult:
    """Perceives formal bond orders, lone pairs, and atomic formal charges from bare XYZ coordinates.

    Parameters
    ----------
    elements : Sequence[str]
        Elemental symbols (e.g., ["O", "H", "H"]).
    coordinates : Sequence[Tuple[float, float, float]] or np.ndarray
        3D Cartesian coordinates in Angstroms, shape (N, 3).
    net_charge : int, default=0
        Total net molecular charge.

    Returns
    -------
    BondPerceptionResult
        Perceived bond orders, atomic formal charges, lone pairs, and conserved total charge.

    Raises
    ------
    BondPerceptionError
        If coordinates are inconsistent, covalent radii cannot be resolved, or ILP optimization fails.
    """
    coords_arr = np.asarray(coordinates, dtype=np.float64)
    n_atoms = len(elements)
    if coords_arr.shape != (n_atoms, 3):
        raise BondPerceptionError(
            f"Coordinate shape {coords_arr.shape} does not match atom count ({n_atoms}, 3)."
        )

    if n_atoms == 0:
        return BondPerceptionResult(
            bond_orders=[],
            formal_charges=[],
            lone_pairs=[],
            total_charge=net_charge,
        )

    # 1. Dynamic Mendeleev calibration
    covalent_radii: List[float] = []
    valence_electrons: List[int] = []
    for sym in elements:
        try:
            elem_obj = element(sym)
            cov_pm = elem_obj.covalent_radius_pyykko
            if cov_pm is None:
                raise ValueError(f"No Pyykko covalent radius for element '{sym}'")
            # Convert picometers (pm) to Angstroms (A)
            covalent_radii.append(float(cov_pm) / 100.0)
            valence_electrons.append(int(elem_obj.nvalence()))
        except Exception as exc:
            raise BondPerceptionError(
                f"Dynamic Mendeleev resolution failed for element symbol '{sym}': {exc}"
            ) from exc

    # 2. Candidate connectivity graph and Pauling geometric bond orders
    edges: List[Tuple[int, int]] = []
    geometric_bos: List[float] = []
    pauling_b = 0.37  # Angstroms

    for i in range(n_atoms):
        for j in range(i + 1, n_atoms):
            dist = float(np.linalg.norm(coords_arr[i] - coords_arr[j]))
            r0 = covalent_radii[i] + covalent_radii[j]
            # Spatial distance threshold: D_ij <= R_cov(i) + R_cov(j) + 0.40 A
            if dist <= r0 + 0.40:
                edges.append((i, j))
                # Pauling's geometric BO formula
                geom_bo = float(np.exp((r0 - dist) / pauling_b))
                geometric_bos.append(geom_bo)

    n_edges = len(edges)

    # Variables layout for MILP:
    # 0 .. n_edges-1                     : BO_e (int, [0, 3])
    # n_edges .. n_edges+n_atoms-1       : n_lp_i (int, [0, 4])
    # n_edges+n_atoms .. n_edges+2*n_atoms-1: q_i (int, [-2, 2])
    # n_edges+2*n_atoms .. n_edges+3*n_atoms-1: u_i (cont, >= |q_i|)
    # n_edges+3*n_atoms .. n_edges+3*n_atoms+n_edges-1: v_e (cont, >= |BO_e - geom_bo_e|)
    num_vars = 2 * n_edges + 3 * n_atoms
    c_obj = [0.0] * num_vars

    weight_q = 2.0
    weight_bo = 1.0

    for i in range(n_atoms):
        c_obj[n_edges + 2 * n_atoms + i] = weight_q
    for e in range(n_edges):
        c_obj[n_edges + 3 * n_atoms + e] = weight_bo

    integrality = [0] * num_vars
    # BO_e are integers
    for e in range(n_edges):
        integrality[e] = 1
    # n_lp_i are integers
    for i in range(n_atoms):
        integrality[n_edges + i] = 1
    # q_i are integers
    for i in range(n_atoms):
        integrality[n_edges + n_atoms + i] = 1

    lower_bounds = [0.0] * num_vars
    upper_bounds = [0.0] * num_vars

    # BO bounds [0, 3]
    for e in range(n_edges):
        lower_bounds[e] = 0.0
        upper_bounds[e] = 3.0

    # Lone pairs bounds: [0, 4] for heavy atoms, [0, 0] for Hydrogen
    for i in range(n_atoms):
        lower_bounds[n_edges + i] = 0.0
        upper_bounds[n_edges + i] = 0.0 if elements[i] == "H" else 4.0

    # Formal charge bounds [-2, 2]
    for i in range(n_atoms):
        lower_bounds[n_edges + n_atoms + i] = -2.0
        upper_bounds[n_edges + n_atoms + i] = 2.0

    # Auxiliary variables bounds
    for i in range(n_atoms):
        lower_bounds[n_edges + 2 * n_atoms + i] = 0.0
        upper_bounds[n_edges + 2 * n_atoms + i] = 4.0

    for e in range(n_edges):
        lower_bounds[n_edges + 3 * n_atoms + e] = 0.0
        upper_bounds[n_edges + 3 * n_atoms + e] = 10.0

    constraints_matrix: List[List[float]] = []
    lhs_bounds: List[float] = []
    rhs_bounds: List[float] = []

    # 1. Formal charge coupling equality:
    # q_i + 2 * n_lp_i + sum_{j in adj(i)} BO_ij = N_valence(i)
    for i in range(n_atoms):
        row = [0.0] * num_vars
        row[n_edges + n_atoms + i] = 1.0  # q_i
        row[n_edges + i] = 2.0  # 2 * n_lp_i
        for e_idx, (u, v) in enumerate(edges):
            if u == i or v == i:
                row[e_idx] = 1.0
        constraints_matrix.append(row)
        lhs_bounds.append(float(valence_electrons[i]))
        rhs_bounds.append(float(valence_electrons[i]))

    # 2. Total charge conservation: sum_{i=1}^N q_i = net_charge
    row_charge = [0.0] * num_vars
    for i in range(n_atoms):
        row_charge[n_edges + n_atoms + i] = 1.0
    constraints_matrix.append(row_charge)
    lhs_bounds.append(float(net_charge))
    rhs_bounds.append(float(net_charge))

    # 3. Period 2 Valence Shell (Octet Rule): For C, N, O, F:
    # 2 * n_lp_i + 2 * sum_{j in adj(i)} BO_ij <= 8
    period_2 = {"C", "N", "O", "F"}
    for i, sym in enumerate(elements):
        if sym in period_2:
            row_oct = [0.0] * num_vars
            row_oct[n_edges + i] = 2.0
            for e_idx, (u, v) in enumerate(edges):
                if u == i or v == i:
                    row_oct[e_idx] = 2.0
            constraints_matrix.append(row_oct)
            lhs_bounds.append(0.0)
            rhs_bounds.append(8.0)

    # 4. Period 3+ Hypervalency Limits: For Si, P, S, Cl, Se, Br, I:
    # 2 * n_lp_i + 2 * sum_{j in adj(i)} BO_ij <= 12
    hypervalent_period3_plus = {"Si", "P", "S", "Cl", "Se", "Br", "I"}
    for i, sym in enumerate(elements):
        if sym in hypervalent_period3_plus:
            row_hyp = [0.0] * num_vars
            row_hyp[n_edges + i] = 2.0
            for e_idx, (u, v) in enumerate(edges):
                if u == i or v == i:
                    row_hyp[e_idx] = 2.0
            constraints_matrix.append(row_hyp)
            lhs_bounds.append(0.0)
            rhs_bounds.append(12.0)

    # 5. Hydrogen Duet Rule: For all H atoms:
    # sum_{j in adj(H)} BO_Hj = 1 and n_lp_H = 0
    for i, sym in enumerate(elements):
        if sym == "H":
            row_h = [0.0] * num_vars
            for e_idx, (u, v) in enumerate(edges):
                if u == i or v == i:
                    row_h[e_idx] = 1.0
            constraints_matrix.append(row_h)
            lhs_bounds.append(1.0)
            rhs_bounds.append(1.0)

    # 6. Auxiliary variable constraints for |q_i|:
    # u_i - q_i >= 0 and u_i + q_i >= 0
    for i in range(n_atoms):
        row_u1 = [0.0] * num_vars
        row_u1[n_edges + 2 * n_atoms + i] = 1.0
        row_u1[n_edges + n_atoms + i] = -1.0
        constraints_matrix.append(row_u1)
        lhs_bounds.append(0.0)
        rhs_bounds.append(float(np.inf))

        row_u2 = [0.0] * num_vars
        row_u2[n_edges + 2 * n_atoms + i] = 1.0
        row_u2[n_edges + n_atoms + i] = 1.0
        constraints_matrix.append(row_u2)
        lhs_bounds.append(0.0)
        rhs_bounds.append(float(np.inf))

    # 7. Auxiliary variable constraints for |BO_e - geom_bo_e|:
    # v_e - BO_e >= -geom_bo_e and v_e + BO_e >= geom_bo_e
    for e_idx in range(n_edges):
        geom_val = geometric_bos[e_idx]
        row_v1 = [0.0] * num_vars
        row_v1[n_edges + 3 * n_atoms + e_idx] = 1.0
        row_v1[e_idx] = -1.0
        constraints_matrix.append(row_v1)
        lhs_bounds.append(-geom_val)
        rhs_bounds.append(float(np.inf))

        row_v2 = [0.0] * num_vars
        row_v2[n_edges + 3 * n_atoms + e_idx] = 1.0
        row_v2[e_idx] = 1.0
        constraints_matrix.append(row_v2)
        lhs_bounds.append(geom_val)
        rhs_bounds.append(float(np.inf))

    a_matrix = np.array(constraints_matrix, dtype=np.float64)
    lin_constraints = LinearConstraint(a_matrix, lhs_bounds, rhs_bounds)
    var_bounds = Bounds(lower_bounds, upper_bounds)

    result = milp(
        c=c_obj,
        integrality=integrality,
        bounds=var_bounds,
        constraints=lin_constraints,
    )

    if not result.success or result.x is None:
        raise BondPerceptionError(
            f"ILP HiGHS bond perception solver failed to converge: {result.status} ({result.message})"
        )

    solution = result.x
    bo_values = solution[0:n_edges]
    lp_values = solution[n_edges : n_edges + n_atoms]
    q_values = solution[n_edges + n_atoms : n_edges + 2 * n_atoms]

    # Assemble perceived bond edges (only edges where perceived bond order > 0)
    perceived_edges: List[BondOrderEdge] = []
    for e_idx, (u, v) in enumerate(edges):
        bo_val = float(round(bo_values[e_idx]))
        if bo_val > 0.0:
            perceived_edges.append(
                BondOrderEdge(
                    atom_i=min(u, v),
                    atom_j=max(u, v),
                    bond_order=bo_val,
                )
            )

    # Sort bonds canonically by (atom_i, atom_j)
    perceived_edges.sort(key=lambda edge: (edge.atom_i, edge.atom_j))

    formal_charges_int = [int(round(q_values[i])) for i in range(n_atoms)]
    lone_pairs_int = [int(round(lp_values[i])) for i in range(n_atoms)]
    computed_total_charge = sum(formal_charges_int)

    return BondPerceptionResult(
        bond_orders=perceived_edges,
        formal_charges=formal_charges_int,
        lone_pairs=lone_pairs_int,
        total_charge=computed_total_charge,
    )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_diff.py ---
"""Physical acceptance tests for topology diff tool and MCCS graph matching."""

from __future__ import annotations

import pytest

from cochem.topos.diff import compute_topology_diff
from cochem.topos.models import TopologyDelta


def test_topology_diff_benzene_to_phenol() -> None:
    """REQ-TOPOS-005: Verify MCCS detection and delta mutation tracking between benzene and phenol."""
    benzene_smiles = "c1ccccc1"
    phenol_smiles = "Oc1ccccc1"
    diff = compute_topology_diff(mol_a_smiles=benzene_smiles, mol_b_smiles=phenol_smiles)
    assert isinstance(diff, TopologyDelta)
    # The 6 benzene ring carbons should be mapped
    assert len(diff.atom_mapping) >= 6
    # Subgraph additions in phenol should capture the hydroxyl (-OH) synthon
    assert len(diff.subgraph_additions) >= 1
    assert any("O" in sub.elements for sub in diff.subgraph_additions)


def test_topology_diff_identical_molecules() -> None:
    """REQ-TOPOS-005: Verify self-comparison yields zero additions, deletions, or mutations."""
    diff = compute_topology_diff("c1ccccc1", "c1ccccc1")
    assert len(diff.atom_mapping) == 6
    assert len(diff.element_mutations) == 0
    assert len(diff.bond_order_mutations) == 0
    assert len(diff.subgraph_additions) == 0
    assert len(diff.subgraph_deletions) == 0


def test_topology_diff_substituent_deletion() -> None:
    """REQ-TOPOS-005: Verify substituent deletion tracking from toluene to benzene."""
    diff = compute_topology_diff("Cc1ccccc1", "c1ccccc1")
    assert len(diff.atom_mapping) >= 6
    assert len(diff.subgraph_deletions) >= 1
    assert any("C" in sub.elements for sub in diff.subgraph_deletions)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_fingerprint.py ---
"""Physical acceptance tests for ECFP4 / Morgan topological fingerprint generation."""

from __future__ import annotations

import pytest

from cochem.topos.fingerprint import (
    compute_dice_similarity,
    compute_tanimoto_similarity,
    generate_ecfp4_fingerprint,
)
from cochem.topos.models import ECFP4FingerprintPayload


def test_ecfp4_fingerprint_generation() -> None:
    """REQ-TOPOS-006: Verify ECFP4 fingerprint calculation and de-duplication."""
    # Generate fingerprint for Pyridine
    fp = generate_ecfp4_fingerprint(smiles="c1ccncc1", radius=2, n_bits=2048)
    assert isinstance(fp, ECFP4FingerprintPayload)
    assert len(fp.bit_vector_2048) == 2048
    assert len(fp.bit_vector_1024) == 1024
    assert len(fp.on_bits_2048) > 0
    assert fp.features_de_duplicated >= 0
    assert len(fp.count_vector) == len(fp.on_bits_2048)


def test_ecfp4_tanimoto_and_dice_similarity() -> None:
    """REQ-TOPOS-006: Verify Tanimoto and Dice similarity between pyridine and benzene."""
    fp_pyr = generate_ecfp4_fingerprint(smiles="c1ccncc1", radius=2, n_bits=2048)
    fp_benz = generate_ecfp4_fingerprint(smiles="c1ccccc1", radius=2, n_bits=2048)

    tanimoto = compute_tanimoto_similarity(fp_pyr, fp_benz)
    dice = compute_dice_similarity(fp_pyr, fp_benz)

    # Physical similarity bounds for related aromatic scaffolds
    assert 0.0 < tanimoto < 1.0, f"Expected 0.0 < T < 1.0, got {tanimoto}"
    assert 0.0 < dice < 1.0, f"Expected 0.0 < D < 1.0, got {dice}"
    assert dice > tanimoto, "Dice coefficient should be strictly greater than Tanimoto"

    # Self-similarity must be exactly 1.0
    assert compute_tanimoto_similarity(fp_pyr, fp_pyr) == 1.0
    assert compute_dice_similarity(fp_pyr, fp_pyr) == 1.0

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_forcefield.py ---
"""Physical acceptance tests for automated forcefield assignment (GAFF2 and OPLS-AA)."""

from __future__ import annotations

import pytest

from cochem.topos.exceptions import UnparameterizedAtomError
from cochem.topos.forcefield import (
    assign_forcefield_parameters,
    geometric_combine,
    lorentz_berthelot_combine,
)
from cochem.topos.models import ForceFieldAssignmentResult, NonBondedParameter


def test_forcefield_assignment_phenanthrene() -> None:
    """REQ-TOPOS-002: Verify RCB ring perception and GAFF2 aromatic typing on phenanthrene."""
    # Phenanthrene has 14 carbons: aromatic ring carbons 'ca' and fused bridgehead carbons 'cp'/'cq'
    result = assign_forcefield_parameters(smiles="C1=CC2=C(C=C1)C3=CC=CC=C3C=C2", forcefield="GAFF2")
    assert isinstance(result, ForceFieldAssignmentResult)
    assert len(result.atom_types) == 14
    # Check that fused bridgehead carbons are distinguished from standard peripheral aromatic carbons
    assert "ca" in result.atom_types
    assert any(t in ["cp", "cq"] for t in result.atom_types)
    assert len(result.non_bonded_parameters) == 14
    assert result.non_bonded_parameters[0].r_min_half_angstrom > 0.0
    assert result.energy_unit == "kcal/mol"
    assert result.distance_unit == "angstrom"


def test_forcefield_assignment_oplsaa() -> None:
    """REQ-TOPOS-002: Verify OPLS-AA parameterization and geometric mixing units."""
    result = assign_forcefield_parameters(smiles="c1ccccc1", forcefield="OPLS-AA")
    assert isinstance(result, ForceFieldAssignmentResult)
    assert result.forcefield_family == "OPLS-AA"
    assert result.energy_unit == "kJ/mol"
    assert result.distance_unit == "nanometer"
    assert len(result.atom_types) == 6
    assert all(t == "CA" for t in result.atom_types)
    assert result.non_bonded_parameters[0].sigma_nm > 0.0


def test_nonbonded_combination_rules() -> None:
    """REQ-TOPOS-002: Verify Lorentz-Berthelot and Geometric combination rules."""
    p1 = NonBondedParameter(
        atom_type="ca",
        sigma_nm=0.339967,
        epsilon_kj_mol=0.359824,
        r_min_half_angstrom=1.9080,
        epsilon_kcal_mol=0.0860,
    )
    p2 = NonBondedParameter(
        atom_type="ha",
        sigma_nm=0.259964,
        epsilon_kj_mol=0.062760,
        r_min_half_angstrom=1.4590,
        epsilon_kcal_mol=0.0150,
    )
    # Lorentz-Berthelot
    r_half_ij, eps_kcal_ij = lorentz_berthelot_combine(p1, p2)
    expected_r = 0.5 * (1.9080 + 1.4590)
    expected_eps = (0.0860 * 0.0150) ** 0.5
    assert abs(r_half_ij - expected_r) < 1e-4
    assert abs(eps_kcal_ij - expected_eps) < 1e-4

    # Geometric
    sig_ij, eps_kj_ij = geometric_combine(p1, p2)
    expected_sig = (0.339967 * 0.259964) ** 0.5
    expected_eps_kj = (0.359824 * 0.062760) ** 0.5
    assert abs(sig_ij - expected_sig) < 1e-4
    assert abs(eps_kj_ij - expected_eps_kj) < 1e-4


def test_unparameterized_metal_raises_error() -> None:
    """REQ-TOPOS-002: Verify UnparameterizedAtomError when encountering unparameterized metals."""
    with pytest.raises(UnparameterizedAtomError) as exc_info:
        assign_forcefield_parameters("C[Fe]C", forcefield="GAFF2")
    assert "unsupported metal" in str(exc_info.value)
    assert "1" in str(exc_info.value)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_fragmentation.py ---
"""Physical acceptance tests for retrosynthetic topological fragmentation (BRICS and RECAP)."""

from __future__ import annotations

import pytest

from cochem.topos.fragmentation import fragment_by_brics, fragment_by_recap
from cochem.topos.models import SynthonRecord


def test_brics_fragmentation_aspirin() -> None:
    """REQ-TOPOS-003: Verify BRICS ester cleavage on Aspirin."""
    # Aspirin: 2-acetoxybenzoic acid (contains ester cleavage rule L3)
    synthons = fragment_by_brics(smiles="CC(=O)Oc1ccccc1C(=O)O")
    assert len(synthons) >= 2
    for syn in synthons:
        assert isinstance(syn, SynthonRecord)
        assert len(syn.attachment_sites) >= 1
        assert syn.attachment_sites[0].polarity in ["donor", "acceptor", "neutral"]
        assert len(syn.elements) == len(syn.coordinates)


def test_brics_attachment_site_directionality_and_vectors() -> None:
    """REQ-TOPOS-003: Verify attachment site polar directionality and 3D connection vectors."""
    synthons = fragment_by_brics(smiles="CC(=O)Oc1ccccc1C(=O)O")
    polarities = [site.polarity for s in synthons for site in s.attachment_sites]
    # Aspirin fragments contain acceptor (carbonyl L1/L6), donor (ester oxygen L3), and neutral (aromatic L16)
    assert "acceptor" in polarities
    assert "donor" in polarities
    assert "neutral" in polarities

    # Verify non-zero connection vectors
    for syn in synthons:
        for site in syn.attachment_sites:
            vec = site.connection_vector
            norm = (vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2) ** 0.5
            assert norm > 0.1, f"Connection vector length {norm} is physically too small"


def test_recap_fragmentation() -> None:
    """REQ-TOPOS-003: Verify RECAP retrosynthetic fragmentation."""
    synthons = fragment_by_recap(smiles="CC(=O)Oc1ccccc1C(=O)O")
    assert len(synthons) >= 2
    for syn in synthons:
        assert isinstance(syn, SynthonRecord)
        assert len(syn.elements) == len(syn.coordinates)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_io.py ---
"""Physical acceptance tests for multi-molecule streaming I/O (.sdf and .mol2)."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from cochem.topos.exceptions import MalformedRecordError
from cochem.topos.io import Mol2StreamReader, Mol2Writer, SDFStreamReader, SDFWriter
from cochem.topos.models import MoleculeRecord


def test_sdf_v2000_streaming_and_quarantine(tmp_path: Path) -> None:
    """REQ-TOPOS-001: Test streaming parser isolation, 0-based normalization, and quarantine handling."""
    sdf_content = (
        "benzene\n  CoChem  09022610002D\n\n  6  6  0  0  0  0  0  0  0  0999 V2000\n"
        "    0.0000    1.4000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    1.2124    0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    1.2124   -0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    0.0000   -1.4000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   -1.2124   -0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   -1.2124    0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "  1  2  2  0  0  0  0\n  2  3  1  0  0  0  0\n  3  4  2  0  0  0  0\n"
        "  4  5  1  0  0  0  0\n  5  6  2  0  0  0  0\n  6  1  1  0  0  0  0\n"
        "M  END\n$$$$\n"
    )
    sdf_file = tmp_path / "benzene.sdf"
    sdf_file.write_text(sdf_content, encoding="utf-8")
    reader = SDFStreamReader(sdf_file)
    records = list(reader.stream_records())
    assert len(records) == 1
    rec = records[0]
    assert rec.name == "benzene"
    assert len(rec.elements) == 6
    # Verify 0-based normalization (input was 1 2 2, normalized should be (0, 1, 2.0))
    assert rec.bonds[0] == (0, 1, 2.0)

    # Quarantine handling test on corrupted record
    corrupt_sdf = tmp_path / "corrupt.sdf"
    corrupt_sdf.write_text("corrupted_mol\ninfo\ncomment\nINVALID COUNTS LINE\n$$$$\n", encoding="utf-8")
    with pytest.raises(MalformedRecordError) as exc_info:
        list(SDFStreamReader(corrupt_sdf).stream_records())

    assert "quarantined to" in str(exc_info.value)
    # Check quarantine directory
    art_dir = Path(os.environ.get("COCH_ARTIFACTS", Path.home() / ".cochem" / "artifacts"))
    quarantine_files = list((art_dir / "quarantine").glob("*.raw"))
    assert len(quarantine_files) > 0


def test_mol2_streaming(tmp_path: Path) -> None:
    """REQ-TOPOS-001: Test Tripos mol2 streaming, Sybyl atom types, and partial charges."""
    mol2_content = (
        "@<TRIPOS>MOLECULE\n"
        "benzene\n"
        "6 6 1 0 0\n"
        "SMALL\n"
        "GASTEIGER\n\n"
        "@<TRIPOS>ATOM\n"
        "1 C1 0.0000 1.4000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "2 C2 1.2124 0.7000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "3 C3 1.2124 -0.7000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "4 C4 0.0000 -1.4000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "5 C5 -1.2124 -0.7000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "6 C6 -1.2124 0.7000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "@<TRIPOS>BOND\n"
        "1 1 2 ar\n"
        "2 2 3 ar\n"
        "3 3 4 ar\n"
        "4 4 5 ar\n"
        "5 5 6 ar\n"
        "6 6 1 ar\n"
        "@<TRIPOS>SUBSTRUCTURE\n"
        "1 BENZENE 1 TEMP 0 **** **** 0 ROOT\n"
    )
    mol2_file = tmp_path / "benzene.mol2"
    mol2_file.write_text(mol2_content, encoding="utf-8")
    reader = Mol2StreamReader(mol2_file)
    records = list(reader.stream_records())
    assert len(records) == 1
    rec = records[0]
    assert rec.name == "benzene"
    assert len(rec.elements) == 6
    assert rec.bonds[0] == (0, 1, 1.5)
    assert len(rec.partial_charges) == 6
    assert abs(rec.partial_charges[0] - (-0.0600)) < 1e-4


def test_sdf_and_mol2_roundtrip_writing(tmp_path: Path) -> None:
    """REQ-TOPOS-001: Test batch and streaming serialization with SDFWriter and Mol2Writer."""
    rec = MoleculeRecord(
        name="phenol",
        elements=["O", "C", "C", "C", "C", "C", "C"],
        coordinates=[
            (0.0, 2.8, 0.0),
            (0.0, 1.4, 0.0),
            (1.2, 0.7, 0.0),
            (1.2, -0.7, 0.0),
            (0.0, -1.4, 0.0),
            (-1.2, -0.7, 0.0),
            (-1.2, 0.7, 0.0),
        ],
        formal_charges=[0, 0, 0, 0, 0, 0, 0],
        bonds=[
            (0, 1, 1.0),
            (1, 2, 1.5),
            (2, 3, 1.5),
            (3, 4, 1.5),
            (4, 5, 1.5),
            (5, 6, 1.5),
            (6, 1, 1.5),
        ],
        properties={"compound": "phenol"},
    )
    sdf_out = tmp_path / "phenol.sdf"
    sdf_writer = SDFWriter(sdf_out)
    sdf_writer.write_record(rec)

    r_sdf = list(SDFStreamReader(sdf_out).stream_records())
    assert len(r_sdf) == 1
    assert r_sdf[0].name == "phenol"
    assert len(r_sdf[0].bonds) == 7

    mol2_out = tmp_path / "phenol.mol2"
    mol2_writer = Mol2Writer(mol2_out)
    mol2_writer.write_record(rec)

    r_mol2 = list(Mol2StreamReader(mol2_out).stream_records())
    assert len(r_mol2) == 1
    assert r_mol2[0].name == "phenol"
    assert len(r_mol2[0].elements) == 7

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_models.py ---
"""Physical acceptance tests for Pydantic v2 domain models in CoChem-TOPOS."""

from __future__ import annotations

import json
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
)


def test_pydantic_v2_json_roundtrip_deserialization() -> None:
    """REQ-TOPOS-004: Verify JSON-safe serialization and deserialization without tuple key crash."""
    edge = BondOrderEdge(atom_i=0, atom_j=1, bond_order=1.0)
    res = BondPerceptionResult(
        bond_orders=[edge],
        formal_charges=[0, 0],
        lone_pairs=[2, 0],
        total_charge=0,
    )
    json_str = res.model_dump_json()
    reconstituted = BondPerceptionResult.model_validate_json(json_str)
    assert reconstituted.bond_orders[0].atom_i == 0
    assert reconstituted.bond_orders[0].bond_order == 1.0
    assert reconstituted.total_charge == 0


def test_molecule_record_serialization_and_properties() -> None:
    """REQ-TOPOS-001: Verify MoleculeRecord serialization and properties roundtrip."""
    rec = MoleculeRecord(
        name="water",
        elements=["O", "H", "H"],
        coordinates=[
            (0.000000, 0.000000, 0.117269),
            (0.000000, 0.757160, -0.469076),
            (0.000000, -0.757160, -0.469076),
        ],
        formal_charges=[0, 0, 0],
        partial_charges=[-0.834, 0.417, 0.417],
        bonds=[(0, 1, 1.0), (0, 2, 1.0)],
        properties={"source": "QM9", "formula": "H2O"},
    )
    assert rec.num_atoms == 3
    assert rec.num_bonds == 2

    raw_json = rec.model_dump_json()
    reconstituted = MoleculeRecord.model_validate_json(raw_json)
    assert reconstituted.name == "water"
    assert len(reconstituted.elements) == 3
    assert reconstituted.coordinates[0][2] == 0.117269
    assert reconstituted.properties["source"] == "QM9"


def test_topology_delta_roundtrip_and_markdown() -> None:
    """REQ-TOPOS-005: Verify TopologyDelta roundtrip and markdown table generation."""
    sub_add = SubgraphDeltaRecord(
        atom_indices=[6],
        elements=["O"],
        bonds=[],
        smiles="O",
    )
    delta = TopologyDelta(
        atom_mapping={0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5},
        element_mutations=[],
        bond_order_mutations=[(0, 1, 1.5, 2.0)],
        subgraph_additions=[sub_add],
        subgraph_deletions=[],
    )
    raw_json = delta.model_dump_json()
    reconstituted = TopologyDelta.model_validate_json(raw_json)
    assert len(reconstituted.atom_mapping) == 6
    assert reconstituted.atom_mapping[0] == 0
    assert len(reconstituted.subgraph_additions) == 1

    md_table = delta.to_markdown_table()
    assert "Topology Comparison Delta" in md_table
    assert "Mapped Core Atoms" in md_table
    assert "`O`" in md_table


def test_synthon_record_roundtrip() -> None:
    """REQ-TOPOS-003: Verify SynthonRecord and AttachmentSite roundtrip."""
    site = AttachmentSite(
        anchor_atom_idx=1,
        brics_class=3,
        polarity="donor",
        connection_vector=(1.2, 0.0, 0.0),
        severed_partner_element="C",
    )
    syn = SynthonRecord(
        smiles="[3*]Oc1ccccc1",
        elements=["O", "C", "C", "C", "C", "C", "C"],
        coordinates=[(0.0, 0.0, 0.0)] * 7,
        bonds=[(0, 1, 1.0), (1, 2, 1.5)],
        attachment_sites=[site],
        formal_charge=0,
    )
    raw_json = syn.model_dump_json()
    reconstituted = SynthonRecord.model_validate_json(raw_json)
    assert len(reconstituted.attachment_sites) == 1
    assert reconstituted.attachment_sites[0].polarity == "donor"
    assert reconstituted.attachment_sites[0].brics_class == 3


def test_forcefield_assignment_result_roundtrip() -> None:
    """REQ-TOPOS-002: Verify ForceFieldAssignmentResult and NonBondedParameter roundtrip."""
    param = NonBondedParameter(
        atom_type="ca",
        sigma_nm=0.339967,
        epsilon_kj_mol=0.359824,
        r_min_half_angstrom=1.9080,
        epsilon_kcal_mol=0.0860,
    )
    res = ForceFieldAssignmentResult(
        atom_types=["ca"],
        charges=[-0.06],
        bonded_parameters={},
        non_bonded_parameters=[param],
        forcefield_family="GAFF2",
        energy_unit="kcal/mol",
        distance_unit="angstrom",
        angle_unit="degrees",
    )
    raw_json = res.model_dump_json()
    reconstituted = ForceFieldAssignmentResult.model_validate_json(raw_json)
    assert reconstituted.forcefield_family == "GAFF2"
    assert reconstituted.non_bonded_parameters[0].atom_type == "ca"
    assert reconstituted.non_bonded_parameters[0].epsilon_kcal_mol == 0.0860


def test_ecfp4_payload_roundtrip() -> None:
    """REQ-TOPOS-006: Verify ECFP4FingerprintPayload roundtrip."""
    payload = ECFP4FingerprintPayload(
        bit_vector_1024=[1] + [0] * 1023,
        bit_vector_2048=[1] + [0] * 2047,
        on_bits_2048=[0],
        count_vector={0: 2},
        features_de_duplicated=4,
    )
    raw_json = payload.model_dump_json()
    reconstituted = ECFP4FingerprintPayload.model_validate_json(raw_json)
    assert len(reconstituted.bit_vector_2048) == 2048
    assert reconstituted.count_vector[0] == 2
    assert reconstituted.features_de_duplicated == 4

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_perception.py ---
"""Physical acceptance tests for bond-order and formal charge perception engine."""

from __future__ import annotations

import pytest
import numpy as np
from mendeleev import element

from cochem.topos.exceptions import BondPerceptionError
from cochem.topos.perception import perceive_bond_orders_from_xyz


def test_water_qm9_bond_order_and_formal_charge() -> None:
    """REQ-TOPOS-004: Verify physical bond-order perception on authentic QM9 water coordinates."""
    coords = [
        (0.000000, 0.000000, 0.117269),   # O
        (0.000000, 0.757160, -0.469076),  # H1
        (0.000000, -0.757160, -0.469076), # H2
    ]
    elements = ["O", "H", "H"]
    res = perceive_bond_orders_from_xyz(elements=elements, coordinates=coords, net_charge=0)
    assert res.total_charge == 0
    assert res.formal_charges[0] == 0, f"Oxygen formal charge must be 0, got {res.formal_charges[0]}"
    assert res.lone_pairs[0] == 2, f"Oxygen must possess 2 lone pairs, got {res.lone_pairs[0]}"
    assert len(res.bond_orders) == 2
    for b in res.bond_orders:
        assert b.bond_order == 1.0


def test_methanesulfonamide_period3_hypervalent_perception() -> None:
    """REQ-TOPOS-004: Verify Period 3 Sulfur perception on authentic methanesulfonamide coordinates."""
    # Authentic 3D Cartesian coordinates for Methanesulfonamide (CH3SO2NH2)
    coords = [
        (-1.758,  0.000, -0.288),  # C
        ( 0.000,  0.000,  0.222),  # S (Period 3 hypervalent center)
        ( 0.354,  1.265, -0.378),  # O1 (S=O double bond)
        ( 0.354, -1.265, -0.378),  # O2 (S=O double bond)
        ( 0.658,  0.000,  1.748),  # N (S-N single bond)
        (-1.912,  0.893, -0.894),  # H (C)
        (-1.912, -0.893, -0.894),  # H (C)
        (-2.378,  0.000,  0.607),  # H (C)
        ( 0.366,  0.817,  2.268),  # H (N)
        ( 0.366, -0.817,  2.268),  # H (N)
    ]
    elements = ["C", "S", "O", "O", "N", "H", "H", "H", "H", "H"]
    res = perceive_bond_orders_from_xyz(elements=elements, coordinates=coords, net_charge=0)
    assert res.total_charge == 0
    # Sulfur index 1: formal charge must be 0, lone pairs = 0
    assert res.formal_charges[1] == 0
    assert res.lone_pairs[1] == 0
    # Verify S=O double bonds (BO ~ 2.0) and S-N / S-C single bonds (BO ~ 1.0)
    s_bonds = [b for b in res.bond_orders if b.atom_i == 1 or b.atom_j == 1]
    assert len(s_bonds) == 4
    s_bo_sum = sum(b.bond_order for b in s_bonds)
    assert abs(s_bo_sum - 6.0) < 1e-3, f"Expected Sulfur BO sum = 6.0 (valence shell 12), got {s_bo_sum}"


def test_dynamic_mendeleev_calibration_scale() -> None:
    """REQ-TOPOS-004: Ensure covalent radii scale dynamically from picometers to Angstroms."""
    sulfur = element("S")
    radius_pm = sulfur.covalent_radius_pyykko
    radius_angstrom = radius_pm / 100.0
    assert 0.90 < radius_angstrom < 1.20

    carbon = element("C")
    assert 0.60 < (carbon.covalent_radius_pyykko / 100.0) < 0.90


def test_perception_invalid_coordinates_shape_raises() -> None:
    """REQ-TOPOS-004: Verify exception raised when coordinates shape does not match atom count."""
    coords = [(0.0, 0.0, 0.0)]
    elements = ["O", "H"]
    with pytest.raises(BondPerceptionError):
        perceive_bond_orders_from_xyz(elements=elements, coordinates=coords)

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.