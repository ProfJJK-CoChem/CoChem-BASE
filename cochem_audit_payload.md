Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260901-suggestions\.in-progress\Perfected_SRS_Chunk_08_TOPOS_Graph_Theory_Part_1_prompts.md.
Original prompt:
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous feature suite specified in Software Requirements Specification (SRS) Chunk 08: `TOPOS_Graph_Theory_Part_1`.

You must implement every component in full adherence to the CoChem Zero-Mock directive, the Tripartite Workspace Air-Gap architecture, the 3-Stage Topological-Spatial-QM Pipeline, the 6-Tier Environment Matrix, and Method Matrix v4. No stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must operate on genuine molecular graphs, physical coordinates, and real physical properties.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Use your tools to inspect the repository layout (under `cochem/topos/` or equivalent domain modules) to locate existing graph, topology, and testing conventions.
2. **Implementation**: Implement all 6 target modules specified below with strict Python 3.10+ PEP 484 type annotations, domain logging, and custom typed exceptions (`TopologyError`, `StericClashError`, `IsomorphismMismatchError`, `ChiralityAssignmentError`).
3. **Physical Test Suite**: Write real, unmocked test suites covering every component with authentic chemical structures (e.g., benzene, pyridine, pyrrole, naphthalene, cubane, L-alanine, D-alanine, (E)/(Z)-but-2-ene, and crowded/clashing conformers).
4. **Physical Verification**: Execute the test suite using `run_command` in the terminal. Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured Execution Result detailing exact file paths created and modified on disk.

---

### MODULE SPECIFICATIONS

#### 1. [TOPOS] Graph Crusher (Macromolecular Coarse-Graining)
- **File Target**: `cochem/topos/coarse_grain.py` (and export in `cochem/topos/__init__.py`)
- **Requirements**:
  - Implement `GraphCrusherConfig` frozen dataclass:
    - `partition_strategy: str = "residue"`
    - `preserve_boundary_bonds: bool = True`
    - `mass_tolerance: float = 1e-5`
    - `charge_tolerance: float = 1e-5`
  - Implement `crush_macromolecule(graph: TopologyGraph, partition_map: dict[int, int], coords: np.ndarray | None = None, config: GraphCrusherConfig | None = None) -> tuple[TopologyGraph, np.ndarray | None]`.
  - **Stage 1 (Topological Partitioning)**:
    - Partition nodes $V = \bigsqcup_B V_B$ using discrete graph quotient partitioning (`networkx.quotient_graph`) based on user-supplied or residue/subgraph partition mappings, ensuring topological contiguity.
    - Calculate and conserve net bead mass $M_B = \sum_{i \in V_B} m_i$ and net bead formal charge $Q_B = \sum_{i \in V_B} q_i$. Atomic masses $m_i$ must be retrieved dynamically via `mendeleev.element(symbol).mass`.
    - Validate mass and charge conservation across the transformation against `mass_tolerance` and `charge_tolerance`. Raise `TopologyError` if conservation fails.
    - Boundary Edge Contraction: Define coarse-grained edges $E_{\text{CG}} = (B_1, B_2) \iff \exists u \in V_{B_1}, v \in V_{B_2}$ such that $(u, v) \in E_{\text{original}}$. Consolidate parallel boundary edges into single topological CG edges carrying aggregated bond orders.
  - **Stage 2 (Spatial Bead Representation)**:
    - When `coords` (shape $(N, 3)$) are provided, calculate center-of-mass coordinates for each bead:
      $$\mathbf{R}_B = \frac{\sum_{i \in V_B} m_i \mathbf{r}_i}{\sum_{i \in V_B} m_i}$$
    - Keep spatial evaluations strictly isolated in Stage 2 without polluting discrete topological graph attributes.

#### 2. [TOPOS] Unified TopologyGraph Subsystem
- **File Target**: `cochem/topos/graph.py`
- **Requirements**:
  - Implement `TopologyGraph` subclassing `networkx.Graph`.
  - **Node Attribute Schema (Topologically Pure)**:
    - Node attributes: `atomic_number: int`, `symbol: str`, `mass: float` (dynamically queried from `mendeleev.element(symbol).mass`), `formal_charge: int`, `hybridization: str` ("sp", "sp2", "sp3"), `in_ring: bool`.
    - Cartesian coordinates (`coords`) MUST be strictly excluded from node attributes to preserve topological invariance across coordinate transformations.
  - **Edge Attribute Schema**:
    - Edge attributes: `bond_order: float` (1.0, 1.5, 2.0, 3.0), `aromatic: bool`, `in_ring: bool`, `stereo: str | None`.
  - **Methods**:
    - `add_chemical_node(node_id: int, symbol: str, formal_charge: int = 0, hybridization: str = "sp3", in_ring: bool = False) -> None`: Validates chemical identity and dynamically sets mass via `mendeleev`.
    - `add_chemical_edge(u: int, v: int, bond_order: float = 1.0, aromatic: bool = False, in_ring: bool = False, stereo: str | None = None) -> None`: Validates chemical valence connectivity.
    - `substructure_search(query: TopologyGraph) -> list[dict[int, int]]`:
      - Integrate `networkx.algorithms.isomorphism.GraphMatcher` implementing the VF2 algorithm.
      - Implement `node_match(n1, n2)` verifying equivalence of `atomic_number`, `formal_charge`, and `hybridization`.
      - Implement `edge_match(e1, e2)` verifying equivalence of `bond_order` and `aromatic` attributes.
      - Return all unique subgraph isomorphism mappings.
    - `to_qcschema_dict(geometry: np.ndarray | None = None) -> dict[str, Any]`:
      - Export all-atom topologies to QCSchema-compliant JSON dictionary (`qcelemental.models.Molecule` format) for $Z \in [1, 118]$.
      - Encapsulate topological attributes (`hybridization`, `in_ring`, aromatic bond orders, CIP stereocenters) within an `extras["cochem_topology"]` dictionary to ensure schema compliance without semantic data loss.
    - Thread-safe serialization: When persisting graph representations to disk, use atomic file replacement protected by `filelock.FileLock`.

#### 3. [TOPOS] Ring Perception & Aromaticity Engine
- **File Target**: `cochem/topos/rings.py`
- **Requirements**:
  - Implement `perceive_cycle_basis(graph: TopologyGraph) -> list[list[int]]`:
    - Compute deterministic, permutation-invariant cycle basis using a polynomial-time cycle basis algorithm (de Pina / Horton) with canonical vertex tie-breaking based on lexicographical order of canonical atom indices.
    - For symmetric polycyclic cage topologies where multiple SSSR exist (e.g., cubane, fullerenes), implement the Smallest Set of Essential Rings (ESSR) / Relevant Cycle basis fallback to guarantee input-order invariance.
    - Annotate graph nodes and edges with `in_ring: bool` and `ring_sizes: list[int]`.
  - Implement `perceive_aromaticity(graph: TopologyGraph, coords: np.ndarray | None = None, planarity_threshold: float = 0.15) -> None`:
    - Identify conjugated cyclic $\pi$-systems.
    - Electron counting: pyridine-like ring heteroatoms donate 1 $\pi$-electron; pyrrole/furan/thiophene-like heteroatoms donate 2 $\pi$-electrons; exocyclic carbonyls/double bonds adjust valence appropriately.
    - Apply Hückel's $(4n + 2)$ rule for monocyclic rings, and Clar's aromatic sextet / perimeter $\pi$-electron counting for fused polycyclics (naphthalene, anthracene, pyrene, phenanthrene).
    - Annotate qualifying nodes with `is_aromatic = True` and qualifying edges with `aromatic = True`, `bond_order = 1.5`.
    - Stage 2 Non-Destructive Planarity Validation: If conformer `coords` are provided, compute geometric planarity strain ($\text{RMSD}_{\text{plane}}$ from best-fit plane) on aromatic rings. Calculate this as a non-destructive physical metric without mutating Stage 1 discrete topological attributes or aromaticity flags.

#### 4. [TOPOS] Graph-Level Stereocenter & Chirality Detector
- **File Target**: `cochem/topos/stereochemistry.py`
- **Requirements**:
  - Implement `assign_tetrahedral_chirality(coords: np.ndarray, center_idx: int, priority_indices: tuple[int, int, int, int]) -> str`:
    - Identify $sp^3$ stereocenters bonded to 4 distinct ligands.
    - Rank ligands (1 > 2 > 3 > 4) following CIP hierarchy: recursive neighbor digraph expansion sorting by atomic number $Z$, then isotopic mass from `mendeleev`.
    - Coordinate-frame-invariant vector triple product parity:
      Given central chiral atom at $\mathbf{r}_0$ and four prioritized ligand coordinates $\mathbf{r}_1, \mathbf{r}_2, \mathbf{r}_3, \mathbf{r}_4$ (where priority $1 > 2 > 3 > 4$), evaluate:
      $$\Delta_{\text{chiral}} = [(\mathbf{r}_1 - \mathbf{r}_0) \times (\mathbf{r}_2 - \mathbf{r}_0)] \cdot (\mathbf{r}_0 - \mathbf{r}_4)$$
      - Line of sight from ligand 4 toward the central atom $\mathbf{r}_0$:
        - $\Delta_{\text{chiral}} < 0 \implies \text{"R"}$ (*Rectus*, clockwise sequence $1 \to 2 \to 3$).
        - $\Delta_{\text{chiral}} > 0 \implies \text{"S"}$ (*Sinister*, counter-clockwise sequence $1 \to 2 \to 3$).
        - $\Delta_{\text{chiral}} == 0 \implies$ raise `ChiralityAssignmentError("Planar or degenerate chiral configuration")`.
  - Implement `assign_double_bond_stereo(coords: np.ndarray, substituent_a: int, terminus_a: int, terminus_b: int, substituent_b: int) -> str`:
    - For double bonds ($sp^2-sp^2$) with two distinct substituents at each terminus ($A$ and $B$).
    - Identify highest-priority CIP substituent $i_{\text{high}}$ on terminus $A$ and $j_{\text{high}}$ on terminus $B$.
    - Calculate 4-atom torsional dihedral angle $\phi(i_{\text{high}}, A, B, j_{\text{high}})$:
      - $|\phi| < 90^\circ \implies \text{"Z"}$ (*Zusammen*, cisoid).
      - $|\phi| \ge 90^\circ \implies \text{"E"}$ (*Entgegen*, transoid).

#### 5. [TOPOS] Custom py3Dmol Jupyter Visualizer Widget
- **File Target**: `cochem/topos/visualization.py`
- **Requirements**:
  - Implement `TOPOSpy3DmolWidget`:
    - `__init__(width: int = 640, height: int = 480) -> None`
    - `@staticmethod def is_headless() -> bool`: Deterministically detect whether running in a headless CI/terminal environment or without an interactive IPython frontend.
    - `render(graph: TopologyGraph, coords: np.ndarray | None = None, style: str = "stick") -> Any`:
      - Serialize `TopologyGraph` nodes, coordinates, and bonds into SDF/PDB or JSON molecular specification.
      - In interactive Jupyter sessions, construct and return a `py3Dmol.glviewer` rendering instance supporting stick, sphere, cartoon, and coarse-grained bead styles.
      - In headless environments, bypass JavaScript rendering gracefully and return a static HTML representation without throwing display errors.
    - `export_html(graph: TopologyGraph, coords: np.ndarray | None = None, output_path: Path | None = None) -> str`: Export a self-contained HTML document with embedded py3Dmol JavaScript payload. Supports saving to disk if `output_path` is specified.

#### 6. [TOPOS] Graph-Based Geometric Clash Detector
- **File Target**: `cochem/topos/clash.py`
- **Requirements**:
  - Implement `ClashPair` frozen dataclass:
    - `atom_i: int`
    - `atom_j: int`
    - `distance: float`
    - `clash_threshold: float`
    - `pair_type: str` ("1-4", "non-bonded", "h-bond")
  - Implement `GeometricClashDetector`:
    - `__init__(k_clash: float = 0.75, k_hbond: float = 0.55, k_14: float = 0.60) -> None`
    - `detect_clashes(coords: np.ndarray, topology: TopologyGraph) -> list[ClashPair]`
  - **Dynamic Van der Waals Overlap & Fallback Hierarchy**:
    - Atomic van der Waals radii $r_{\text{vdw}}$ MUST be queried dynamically from `mendeleev.element(symbol)` with strict `NoneType` guarding before unit conversion (convert pm to Å by dividing by 100.0):
      1. Primary Query: `elem.vdw_radius / 100.0` (if `elem.vdw_radius is not None`).
      2. Fallback 1: `elem.vdw_radius_alvarez / 100.0` (if `elem.vdw_radius_alvarez is not None`).
      3. Fallback 2: `elem.vdw_radius_bondi / 100.0` (if `elem.vdw_radius_bondi is not None`).
      4. Fallback 3 (Superheavy Transactinides $Z \in [104, 118]$): For elements where VdW tables are unpopulated in `mendeleev`, query `elem.covalent_radius_pyykko` (or `elem.covalent_radius_cordero`) and compute $r_{\text{vdw}} = 1.60 \cdot r_{\text{cov}} / 100.0$.
      5. Exception Handling: If all queries evaluate to `None`, raise `StericClashError(f"Undefined Van der Waals and covalent radii for element {symbol} (Z={Z})")`. Static hardcoded dictionaries or fallbacks to dummy constants are strictly forbidden.
  - **Overlap Thresholds & Topological Exclusion Masks**:
    - Exclude 1-2 (bonded) and 1-3 (geminal) pairs using graph shortest-path topological distance on `topology`.
    - 1-4 (torsional) pairs: Clash threshold = $k_{14} \cdot (r_{\text{vdw}, i} + r_{\text{vdw}, j})$ with $k_{14} = 0.60$.
    - Hydrogen bond pairs: For polar donor-acceptor pairs involving hydrogen ($H \cdots O, H \cdots N, H \cdots F$), apply relaxed threshold with $k_{\text{hbond}} = 0.55$.
    - Non-bonded pairs: Clash threshold = $k_{\text{clash}} \cdot (r_{\text{vdw}, i} + r_{\text{vdw}, j})$ with $k_{\text{clash}} = 0.75$.
    - A clash is detected whenever $d_{ij} < \text{threshold}$.
  - **Spatial Acceleration**:
    - Use `scipy.spatial.cKDTree` for bounding-volume distance queries to achieve $O(N \log N)$ distance filtering.
    - Gate conformers for downstream Method Matrix v4 tiers (`T1-1min` / `T1-1h`).

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate**:
   - Every function and class must be fully operational and complete.
   - Absolutely NO `pass` stubs, NO `NotImplementedError`, NO synthetic mocks, and NO tautological test assertions.
2. **Mendeleev Mandate**:
   - Atomic masses, isotopic masses, and VdW radii must be queried dynamically via `mendeleev.element(symbol)`.
   - Never hardcode mass or radius tables.
3. **Tripartite Workspace Air-Gap**:
   - Source code resides strictly in Tier 1 (git repo).
   - Scratch wavefunctions, temporary geometries, and ephemeral scratch must use `tempfile.gettempdir()` / `/tmp/cochem_exec_<uuid>/` (Tier 3).
   - Persistent artifacts must use `$COCHEM_ARTIFACT_DIR` protected by `filelock.FileLock` (Tier 2).
4. **Cross-Platform Portability**:
   - Use `pathlib.Path` for all path manipulations. Do not hardcode `/tmp/` or Windows-specific separators.
   - Run deterministically on CPU without locking or requiring CUDA contexts.

---

### ACTION PLAN FOR CODER

1. Create or update the implementation modules:
   - `cochem/topos/graph.py`
   - `cochem/topos/coarse_grain.py`
   - `cochem/topos/rings.py`
   - `cochem/topos/stereochemistry.py`
   - `cochem/topos/visualization.py`
   - `cochem/topos/clash.py`
   - `cochem/topos/__init__.py`
2. Create comprehensive test suites:
   - `tests/topos/test_topology_graph.py`
   - `tests/topos/test_coarse_grain.py`
   - `tests/topos/test_rings_aromaticity.py`
   - `tests/topos/test_stereochemistry.py`
   - `tests/topos/test_visualization.py`
   - `tests/topos/test_clash_detector.py`
3. Execute tests via terminal (`pytest tests/topos/ -v`) and verify 100% pass rate.
4. Output the complete list of touched and created files in your final execution report.
I have dispatched the generated chunked prompt to `cochem-audit` ([`764089f3-b35a-45d4-bdb3-a68f3ad9fab6`](conversation://764089f3-b35a-45d4-bdb3-a68f3ad9fab6)) for adversarial ratification against the Zero-Mock directive, the Mendeleev mandate, and Method Matrix v4 compliance. Awaiting the auditor's formal verdict.
The `cochem-audit` agent is actively running physical verification scripts on the mathematical and chemical logic (including vector triple product parity, torsional dihedral boundaries, and transactinide Mendeleev fallback chains). Awaiting final audit verdict.
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous feature suite specified in Software Requirements Specification (SRS) Chunk 08: `TOPOS_Graph_Theory_Part_1`.

You must implement every component in full adherence to the CoChem Zero-Mock directive, the Tripartite Workspace Air-Gap architecture, the 3-Stage Topological-Spatial-QM Pipeline, the 6-Tier Environment Matrix, and Method Matrix v4. No stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must operate on genuine molecular graphs, physical coordinates, and real physical properties.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Use your tools to inspect the repository layout (under `cochem/topos/` or equivalent domain modules) to locate existing graph, topology, and testing conventions.
2. **Implementation**: Implement all 6 target modules specified below with strict Python 3.10+ PEP 484 type annotations, domain logging, and custom typed exceptions (`TopologyError`, `StericClashError`, `IsomorphismMismatchError`, `ChiralityAssignmentError`).
3. **Physical Test Suite**: Write real, unmocked test suites covering every component with authentic chemical structures (e.g., benzene, pyridine, pyrrole, naphthalene, cubane, L-alanine, D-alanine, (E)/(Z)-but-2-ene, and crowded/clashing conformers).
4. **Physical Verification**: Execute the test suite using `run_command` in the terminal. Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured Execution Result detailing exact file paths created and modified on disk.

---

### MODULE SPECIFICATIONS

#### 1. [TOPOS] Graph Crusher (Macromolecular Coarse-Graining)
- **File Target**: `cochem/topos/coarse_grain.py` (and export in `cochem/topos/__init__.py`)
- **Requirements**:
  - Implement `GraphCrusherConfig` frozen dataclass:
    - `partition_strategy: str = "residue"`
    - `preserve_boundary_bonds: bool = True`
    - `mass_tolerance: float = 1e-5`
    - `charge_tolerance: float = 1e-5`
  - Implement `crush_macromolecule(graph: TopologyGraph, partition_map: dict[int, int], coords: np.ndarray | None = None, config: GraphCrusherConfig | None = None) -> tuple[TopologyGraph, np.ndarray | None]`.
  - **Stage 1 (Topological Partitioning)**:
    - Partition nodes $V = \bigsqcup_B V_B$ using discrete graph quotient partitioning (`networkx.quotient_graph`) based on user-supplied or residue/subgraph partition mappings, ensuring topological contiguity.
    - Calculate and conserve net bead mass $M_B = \sum_{i \in V_B} m_i$ and net bead formal charge $Q_B = \sum_{i \in V_B} q_i$. Atomic masses $m_i$ must be retrieved dynamically via `mendeleev.element(symbol).mass`.
    - Validate mass and charge conservation across the transformation against `mass_tolerance` and `charge_tolerance`. Raise `TopologyError` if conservation fails.
    - Boundary Edge Contraction: Define coarse-grained edges $E_{\text{CG}} = (B_1, B_2) \iff \exists u \in V_{B_1}, v \in V_{B_2}$ such that $(u, v) \in E_{\text{original}}$. Consolidate parallel boundary edges into single topological CG edges carrying aggregated bond orders.
  - **Stage 2 (Spatial Bead Representation)**:
    - When `coords` (shape $(N, 3)$) are provided, calculate center-of-mass coordinates for each bead:
      $$\mathbf{R}_B = \frac{\sum_{i \in V_B} m_i \mathbf{r}_i}{\sum_{i \in V_B} m_i}$$
    - Keep spatial evaluations strictly isolated in Stage 2 without polluting discrete topological graph attributes.

#### 2. [TOPOS] Unified TopologyGraph Subsystem
- **File Target**: `cochem/topos/graph.py`
- **Requirements**:
  - Implement `TopologyGraph` subclassing `networkx.Graph`.
  - **Node Attribute Schema (Topologically Pure)**:
    - Node attributes: `atomic_number: int`, `symbol: str`, `mass: float` (dynamically queried from `mendeleev.element(symbol).mass`), `formal_charge: int`, `hybridization: str` ("sp", "sp2", "sp3"), `in_ring: bool`.
    - Cartesian coordinates (`coords`) MUST be strictly excluded from node attributes to preserve topological invariance across coordinate transformations.
  - **Edge Attribute Schema**:
    - Edge attributes: `bond_order: float` (1.0, 1.5, 2.0, 3.0), `aromatic: bool`, `in_ring: bool`, `stereo: str | None`.
  - **Methods**:
    - `add_chemical_node(node_id: int, symbol: str, formal_charge: int = 0, hybridization: str = "sp3", in_ring: bool = False) -> None`: Validates chemical identity and dynamically sets mass via `mendeleev`.
    - `add_chemical_edge(u: int, v: int, bond_order: float = 1.0, aromatic: bool = False, in_ring: bool = False, stereo: str | None = None) -> None`: Validates chemical valence connectivity.
    - `substructure_search(query: TopologyGraph) -> list[dict[int, int]]`:
      - Integrate `networkx.algorithms.isomorphism.GraphMatcher` implementing the VF2 algorithm.
      - Implement `node_match(n1, n2)` verifying equivalence of `atomic_number`, `formal_charge`, and `hybridization`.
      - Implement `edge_match(e1, e2)` verifying equivalence of `bond_order` and `aromatic` attributes.
      - Return all unique subgraph isomorphism mappings.
    - `to_qcschema_dict(geometry: np.ndarray | None = None) -> dict[str, Any]`:
      - Export all-atom topologies to QCSchema-compliant JSON dictionary (`qcelemental.models.Molecule` format) for $Z \in [1, 118]$.
      - Encapsulate topological attributes (`hybridization`, `in_ring`, aromatic bond orders, CIP stereocenters) within an `extras["cochem_topology"]` dictionary to ensure schema compliance without semantic data loss.
    - Thread-safe serialization: When persisting graph representations to disk, use atomic file replacement protected by `filelock.FileLock`.

#### 3. [TOPOS] Ring Perception & Aromaticity Engine
- **File Target**: `cochem/topos/rings.py`
- **Requirements**:
  - Implement `perceive_cycle_basis(graph: TopologyGraph) -> list[list[int]]`:
    - Compute deterministic, permutation-invariant cycle basis using a polynomial-time cycle basis algorithm (de Pina / Horton) with canonical vertex tie-breaking based on lexicographical order of canonical atom indices.
    - For symmetric polycyclic cage topologies where multiple SSSR exist (e.g., cubane, fullerenes), implement the Smallest Set of Essential Rings (ESSR) / Relevant Cycle basis fallback to guarantee input-order invariance.
    - Annotate graph nodes and edges with `in_ring: bool` and `ring_sizes: list[int]`.
  - Implement `perceive_aromaticity(graph: TopologyGraph, coords: np.ndarray | None = None, planarity_threshold: float = 0.15) -> None`:
    - Identify conjugated cyclic $\pi$-systems.
    - Electron counting: pyridine-like ring heteroatoms donate 1 $\pi$-electron; pyrrole/furan/thiophene-like heteroatoms donate 2 $\pi$-electrons; exocyclic carbonyls/double bonds adjust valence appropriately.
    - Apply Hückel's $(4n + 2)$ rule for monocyclic rings, and Clar's aromatic sextet / perimeter $\pi$-electron counting for fused polycyclics (naphthalene, anthracene, pyrene, phenanthrene).
    - Annotate qualifying nodes with `is_aromatic = True` and qualifying edges with `aromatic = True`, `bond_order = 1.5`.
    - Stage 2 Non-Destructive Planarity Validation: If conformer `coords` are provided, compute geometric planarity strain ($\text{RMSD}_{\text{plane}}$ from best-fit plane) on aromatic rings. Calculate this as a non-destructive physical metric without mutating Stage 1 discrete topological attributes or aromaticity flags.

#### 4. [TOPOS] Graph-Level Stereocenter & Chirality Detector
- **File Target**: `cochem/topos/stereochemistry.py`
- **Requirements**:
  - Implement `assign_tetrahedral_chirality(coords: np.ndarray, center_idx: int, priority_indices: tuple[int, int, int, int]) -> str`:
    - Identify $sp^3$ stereocenters bonded to 4 distinct ligands.
    - Rank ligands (1 > 2 > 3 > 4) following CIP hierarchy: recursive neighbor digraph expansion sorting by atomic number $Z$, then isotopic mass from `mendeleev`.
    - Coordinate-frame-invariant vector triple product parity:
      Given central chiral atom at $\mathbf{r}_0$ and four prioritized ligand coordinates $\mathbf{r}_1, \mathbf{r}_2, \mathbf{r}_3, \mathbf{r}_4$ (where priority $1 > 2 > 3 > 4$), evaluate:
      $$\Delta_{\text{chiral}} = [(\mathbf{r}_1 - \mathbf{r}_0) \times (\mathbf{r}_2 - \mathbf{r}_0)] \cdot (\mathbf{r}_0 - \mathbf{r}_4)$$
      - Line of sight from ligand 4 toward the central atom $\mathbf{r}_0$:
        - $\Delta_{\text{chiral}} < 0 \implies \text{"R"}$ (*Rectus*, clockwise sequence $1 \to 2 \to 3$).
        - $\Delta_{\text{chiral}} > 0 \implies \text{"S"}$ (*Sinister*, counter-clockwise sequence $1 \to 2 \to 3$).
        - $\Delta_{\text{chiral}} == 0 \implies$ raise `ChiralityAssignmentError("Planar or degenerate chiral configuration")`.
  - Implement `assign_double_bond_stereo(coords: np.ndarray, substituent_a: int, terminus_a: int, terminus_b: int, substituent_b: int) -> str`:
    - For double bonds ($sp^2-sp^2$) with two distinct substituents at each terminus ($A$ and $B$).
    - Identify highest-priority CIP substituent $i_{\text{high}}$ on terminus $A$ and $j_{\text{high}}$ on terminus $B$.
    - Calculate 4-atom torsional dihedral angle $\phi(i_{\text{high}}, A, B, j_{\text{high}})$:
      - $|\phi| < 90^\circ \implies \text{"Z"}$ (*Zusammen*, cisoid).
      - $|\phi| \ge 90^\circ \implies \text{"E"}$ (*Entgegen*, transoid).

#### 5. [TOPOS] Custom py3Dmol Jupyter Visualizer Widget
- **File Target**: `cochem/topos/visualization.py`
- **Requirements**:
  - Implement `TOPOSpy3DmolWidget`:
    - `__init__(width: int = 640, height: int = 480) -> None`
    - `@staticmethod def is_headless() -> bool`: Deterministically detect whether running in a headless CI/terminal environment or without an interactive IPython frontend.
    - `render(graph: TopologyGraph, coords: np.ndarray | None = None, style: str = "stick") -> Any`:
      - Serialize `TopologyGraph` nodes, coordinates, and bonds into SDF/PDB or JSON molecular specification.
      - In interactive Jupyter sessions, construct and return a `py3Dmol.glviewer` rendering instance supporting stick, sphere, cartoon, and coarse-grained bead styles.
      - In headless environments, bypass JavaScript rendering gracefully and return a static HTML representation without throwing display errors.
    - `export_html(graph: TopologyGraph, coords: np.ndarray | None = None, output_path: Path | None = None) -> str`: Export a self-contained HTML document with embedded py3Dmol JavaScript payload. Supports saving to disk if `output_path` is specified.

#### 6. [TOPOS] Graph-Based Geometric Clash Detector
- **File Target**: `cochem/topos/clash.py`
- **Requirements**:
  - Implement `ClashPair` frozen dataclass:
    - `atom_i: int`
    - `atom_j: int`
    - `distance: float`
    - `clash_threshold: float`
    - `pair_type: str` ("1-4", "non-bonded", "h-bond")
  - Implement `GeometricClashDetector`:
    - `__init__(k_clash: float = 0.75, k_hbond: float = 0.55, k_14: float = 0.60) -> None`
    - `detect_clashes(coords: np.ndarray, topology: TopologyGraph) -> list[ClashPair]`
  - **Dynamic Van der Waals Overlap & Fallback Hierarchy**:
    - Atomic van der Waals radii $r_{\text{vdw}}$ MUST be queried dynamically from `mendeleev.element(symbol)` with strict `NoneType` guarding before unit conversion (convert pm to Å by dividing by 100.0):
      1. Primary Query: `elem.vdw_radius / 100.0` (if `elem.vdw_radius is not None`).
      2. Fallback 1: `elem.vdw_radius_alvarez / 100.0` (if `elem.vdw_radius_alvarez is not None`).
      3. Fallback 2: `elem.vdw_radius_bondi / 100.0` (if `elem.vdw_radius_bondi is not None`).
      4. Fallback 3 (Superheavy Transactinides $Z \in [104, 118]$): For elements where VdW tables are unpopulated in `mendeleev`, query `elem.covalent_radius_pyykko` (or `elem.covalent_radius_cordero`) and compute $r_{\text{vdw}} = 1.60 \cdot r_{\text{cov}} / 100.0$.
      5. Exception Handling: If all queries evaluate to `None`, raise `StericClashError(f"Undefined Van der Waals and covalent radii for element {symbol} (Z={Z})")`. Static hardcoded dictionaries or fallbacks to dummy constants are strictly forbidden.
  - **Overlap Thresholds & Topological Exclusion Masks**:
    - Exclude 1-2 (bonded) and 1-3 (geminal) pairs using graph shortest-path topological distance on `topology`.
    - 1-4 (torsional) pairs: Clash threshold = $k_{14} \cdot (r_{\text{vdw}, i} + r_{\text{vdw}, j})$ with $k_{14} = 0.60$.
    - Hydrogen bond pairs: For polar donor-acceptor pairs involving hydrogen ($H \cdots O, H \cdots N, H \cdots F$), apply relaxed threshold with $k_{\text{hbond}} = 0.55$.
    - Non-bonded pairs: Clash threshold = $k_{\text{clash}} \cdot (r_{\text{vdw}, i} + r_{\text{vdw}, j})$ with $k_{\text{clash}} = 0.75$.
    - A clash is detected whenever $d_{ij} < \text{threshold}$.
  - **Spatial Acceleration**:
    - Use `scipy.spatial.cKDTree` for bounding-volume distance queries to achieve $O(N \log N)$ distance filtering.
    - Gate conformers for downstream Method Matrix v4 tiers (`T1-1min` / `T1-1h`).

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate**:
   - Every function and class must be fully operational and complete.
   - Absolutely NO `pass` stubs, NO `NotImplementedError`, NO synthetic mocks, and NO tautological test assertions.
2. **Mendeleev Mandate**:
   - Atomic masses, isotopic masses, and VdW radii must be queried dynamically via `mendeleev.element(symbol)`.
   - Never hardcode mass or radius tables.
3. **Tripartite Workspace Air-Gap**:
   - Source code resides strictly in Tier 1 (git repo).
   - Scratch wavefunctions, temporary geometries, and ephemeral scratch must use `tempfile.gettempdir()` / `/tmp/cochem_exec_<uuid>/` (Tier 3).
   - Persistent artifacts must use `$COCHEM_ARTIFACT_DIR` protected by `filelock.FileLock` (Tier 2).
4. **Cross-Platform Portability**:
   - Use `pathlib.Path` for all path manipulations. Do not hardcode `/tmp/` or Windows-specific separators.
   - Run deterministically on CPU without locking or requiring CUDA contexts.

---

### ACTION PLAN FOR CODER

1. Create or update the implementation modules:
   - `cochem/topos/graph.py`
   - `cochem/topos/coarse_grain.py`
   - `cochem/topos/rings.py`
   - `cochem/topos/stereochemistry.py`
   - `cochem/topos/visualization.py`
   - `cochem/topos/clash.py`
   - `cochem/topos/__init__.py`
2. Create comprehensive test suites:
   - `tests/topos/test_topology_graph.py`
   - `tests/topos/test_coarse_grain.py`
   - `tests/topos/test_rings_aromaticity.py`
   - `tests/topos/test_stereochemistry.py`
   - `tests/topos/test_visualization.py`
   - `tests/topos/test_clash_detector.py`
3. Execute tests via terminal (`pytest tests/topos/ -v`) and verify 100% pass rate.
4. Output the complete list of touched and created files in your final execution report.
Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.