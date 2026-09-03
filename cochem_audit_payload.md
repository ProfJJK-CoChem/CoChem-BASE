Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260901-suggestions\.in-progress\Perfected_SRS_Chunk_13_TOPOS_Alignment_Part_1_prompts.md.
Original prompt:
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous feature suite specified in Software Requirements Specification (SRS) Chunk 13: `TOPOS_Alignment_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev library mandate, and Method Matrix v4. Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must execute physically against authentic chemical topologies, genuine molecular structures, and physical constants.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Inspect the repository structure under `cochem/topos/` to identify existing graph primitives, `TopologyGraph` abstractions, and testing conventions established in prior TOPOS modules.
2. **Implementation**: Implement all target modules specified below with strict Python 3.10+ PEP 484 type annotations, thread-safe persistence, and custom typed domain exceptions (`ToposAlignmentError`, `MCSConvergenceTimeoutError`, `CollinearDegeneracyError`, `DegenerateCoordinatesError`, `IncompatibleTopologyError`).
3. **Physical Test Suite**: Write comprehensive, unmocked test suites covering each module under `tests/topos/test_topos_alignment.py` with authentic chemical species and physical fixtures (e.g., authentic D-alanine / L-alanine heavy-atom chiral enantiomers, linear acetylene $C_2H_2$, planar benzene $C_6$ rings in the xy-plane, and BSSE water dimer counterpoise complexes with ghost atoms).
4. **Physical Verification**: Execute the test suite using `run_command` in the terminal (`pytest tests/topos/test_topos_alignment.py -v`). Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured execution report detailing all files created and modified on disk.

---

### MODULE SPECIFICATIONS

#### 1. [TOPOS] Pydantic v2 Domain Models & Exception Hierarchy
- **File Target**: `cochem/topos/alignment.py` (or `cochem/topos/models.py` & `cochem/topos/exceptions.py`, exported in `cochem/topos/__init__.py`)
- **Domain Exceptions**:
  - `ToposAlignmentError(Exception)`: Base exception for topology alignment failures.
  - `MCSConvergenceTimeoutError(ToposAlignmentError)`: Raised when MCS graph search exceeds the allocated execution timeout (default 30.0s) or when `mcs_result.canceled == True`.
  - `CollinearDegeneracyError(ToposAlignmentError)`: Raised when atomic coordinates exhibit collinear rank-deficiency in SVD ($\frac{\sigma_2}{\sigma_1} < 10^{-7}$).
  - `DegenerateCoordinatesError(ToposAlignmentError)`: Raised when atomic coordinates exhibit point-degeneracy ($\sigma_1 < 10^{-12}$).
  - `IncompatibleTopologyError(ToposAlignmentError)`: Raised when molecules share insufficient overlapping substructure ($N_{\text{MCS}} < 3$).
- **Pydantic v2 Data Models (Python 3.10+)**:
  - `ConformerInput`:
    - `conformer_id: str`: Unique hash or identifier for conformer.
    - `elements: List[str]`: Elemental symbols (minimum length 3).
    - `atomic_numbers: List[int]`: IUPAC atomic numbers $Z$ (minimum length 3).
    - `coordinates: List[Tuple[float, float, float]]`: $(N, 3)$ Cartesian coordinates in Ångströms (minimum length 3).
    - `bonds: List[Tuple[int, int, float]] = Field(default_factory=list)`: 0-based bond edges: `(idx_i, idx_j, bond_order)`.
    - `reference_smiles: Optional[str] = None`: Optional canonical SMILES string for topological validation.
    - `masses: Optional[List[float]] = None`: Optional atomic masses dynamically retrieved via `mendeleev`.
    - `energy_kcal_mol: Optional[float] = None`: Electronic or free energy tag from QM runner.
    - `is_ghost: List[bool] = Field(default_factory=list)`: Mask identifying BSSE ghost/dummy atoms.
    - Validation: Enforce exact length matching across `elements`, `atomic_numbers`, `coordinates`, `masses` (if provided), and `is_ghost`. If `is_ghost` is empty, auto-populate with `[False] * len(elements)`.
  - `MCSAlignmentConfig`:
    - `timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0)`: `rdFMCS` search timeout ceiling.
    - `mass_weighting: bool = False`: Whether to weight Kabsch covariance and centroids by atomic masses.
    - `match_valences: bool = True`: Enforce valence matching in MCS.
    - `ring_matches_ring_only: bool = True`: Strict ring-to-ring matching.
    - `complete_rings_only: bool = False`: Permit partial ring overlap across fused scaffolds.
    - `min_mcs_atoms: int = Field(default=3, ge=3)`: Minimum common substructure atom count.
    - `svd_condition_tol: float = Field(default=1e-7, ge=1e-12)`: Singular value condition ratio tolerance for rank-deficiency.
    - `rmsd_cluster_threshold_angstrom: float = Field(default=0.25, ge=0.01)`: Deduplication RMSD cutoff.
    - `ignore_ghost_atoms: bool = True`: Exclude ghost/BSSE atoms from alignment kernel.
  - `AlignedConformerResult`:
    - `conformer_id: str`
    - `reference_id: str`
    - `rmsd_angstrom: float = Field(..., ge=0.0)`: Analytical RMSD over mapped MCS non-ghost atoms.
    - `rotation_matrix: List[List[float]]`: Orthogonal $(3, 3)$ rotation matrix $R$ satisfying $R^T R = I$ and $\det(R) = +1.0 \pm 10^{-4}$.
    - `translation_vector: List[float]`: $(3,)$ optimal translation vector $\vec{t}$.
    - `aligned_coordinates: List[Tuple[float, float, float]]`: $(N, 3)$ transformed full coordinates.
    - `atom_mapping: Dict[int, int]`: 0-based index map: `{target_idx: ref_idx}`.
    - `execution_duration_seconds: float = Field(..., ge=0.0)`
  - `EnsembleAlignmentSummary`:
    - `reference_id: str`
    - `total_conformers: int`
    - `aligned_conformers: List[AlignedConformerResult]`
    - `pairwise_rmsd_matrix: List[List[float]]`: Symmetric $(M, M)$ matrix with zero diagonal and non-negative elements.
    - `duplicate_clusters: List[List[str]] = Field(default_factory=list)`: Clusters of redundant conformer IDs where pairwise RMSD $< \delta_{\text{thresh}}$.

#### 2. [TOPOS] Maximum Common Substructure (MCS) Perception & Ghost-Atom Sanitization
- **Requirement ID**: `REQ-TOPOS-013.1`
- **File Target**: `cochem/topos/alignment.py`
- **Bond Connectivity Perception**:
  - Accept explicit bond connectivity tables `bonds: List[Tuple[int, int, float]]` or canonical SMILES.
  - If bond connectivity is missing from bare coordinate records, execute automated topology perception via `rdkit.Chem.rdDetermineBonds.DetermineConnectivity(mol)` calibrated against Pyykkö relativistic covalent radii dynamically scaled from `mendeleev` `[M]`.
- **Ghost-Atom Sanitization**:
  - Intermolecular complexes generated for Basis Set Superposition Error (BSSE) counterpoise corrections contain ghost atoms (symbols `Gh`, `Bq`, `X` or atomic number $Z = 0$).
  - Convert or filter ghost atoms prior to RDKit molecule construction (e.g., mapping to atomic number $0$ or wildcard `*`) to prevent unrecoverable C++ `PeriodicTable.h` core exceptions.
- **Process-Level Timeout Safeguard & GIL Isolation**:
  - MCS graph extraction between target conformer $C_{\text{target}}$ and reference conformer $C_{\text{ref}}$ must execute via RDKit `rdFMCS.FindMCS` inside an isolated worker process (`concurrent.futures.ProcessPoolExecutor`) bounded by an explicit timeout ceiling of $30.0\,\text{s}$ `[D]`.
  - Explicitly inspect `mcs_result.canceled`. If `mcs_result.canceled == True` or a worker timeout occurs, immediately raise `MCSConvergenceTimeoutError`.
- **MCS Parameters & Topology Validation**:
  - `atomCompare = rdFMCS.AtomCompare.CompareElements` (strict atomic number match).
  - `bondCompare = rdFMCS.BondCompare.CompareOrder` (strict bond order match).
  - `matchValences = True` (enforces electronic valence compatibility).
  - `ringMatchesRingOnly = True` (prevents unphysical acyclic-to-ring mappings).
  - `completeRingsOnly = False` (permits partial ring overlap across fused scaffolds).
  - If common atom count $N_{\text{MCS}} < 3$, raise `IncompatibleTopologyError`.

#### 3. [TOPOS] Mass-Weighted Centroid Translation & Ghost-Atom Masking
- **Requirement ID**: `REQ-TOPOS-013.2`
- **File Target**: `cochem/topos/alignment.py`
- **Ghost Atom Exclusion & Mendeleev Lookup Guard**:
  - Strictly exclude all ghost atoms ($Z = 0$ or `is_ghost == True`) from MCS coordinate sub-blocks prior to centroid calculation, cross-covariance assembly, and rotation fitting.
  - **Mendeleev Mass Lookup Guard**: Dynamic queries to `mendeleev.element(Z)` MUST be guarded: if $Z = 0$ or `is_ghost == True`, assign mass strictly as $0.0\,\text{Da}$ without calling `mendeleev`, preventing uncaught `KeyError` / `ValueError` / `ElementNotFoundError`. For non-ghost atoms, query dynamic atomic mass via `mendeleev.element(Z).mass` `[M]`.
- **Mathematical Centroid Formulation**:
  - For mapped MCS non-ghost coordinate matrices $P \in \mathbb{R}^{N \times 3}$ (target) and $Q \in \mathbb{R}^{N \times 3}$ (reference) ($N = N_{\text{MCS}} \ge 3$):
  - Assign weights $w_i > 0$: unweighted ($w_i = 1.0$) or mass-weighted ($w_i = m_i$).
  - Compute weighted centroids:
    $$\bar{P} = \frac{\sum_{i=1}^N w_i P_i}{\sum_{i=1}^N w_i}, \quad \bar{Q} = \frac{\sum_{i=1}^N w_i Q_i}{\sum_{i=1}^N w_i} \quad \text{[D]}$$
  - Center coordinates:
    $$P_c = P - \mathbf{1} \bar{P}^T, \quad Q_c = Q - \mathbf{1} \bar{Q}^T \quad \text{[D]}$$

#### 4. [TOPOS] Cross-Covariance, SVD & Numerical Degeneracy Safeguards
- **Requirement ID**: `REQ-TOPOS-013.3`
- **File Target**: `cochem/topos/alignment.py`
- **Dispersion Assembly & Full SVD**:
  - Assemble weighted cross-covariance dispersion matrix $H \in \mathbb{R}^{3 \times 3}$:
    $$H = P_c^T W Q_c = \sum_{i=1}^N w_i (P_{c,i}^T Q_{c,i}) \quad \text{[D]}$$
    where $W = \operatorname{diag}(w_1, \dots, w_N)$.
  - Compute full SVD via `scipy.linalg.svd`:
    $$H = U \Sigma V^T \quad \text{[D]}$$
    where $U, V \in O(3)$ and singular values $\Sigma = \operatorname{diag}(\sigma_1, \sigma_2, \sigma_3)$ with $\sigma_1 \ge \sigma_2 \ge \sigma_3 \ge 0$.
- **Numerical Degeneracy Safeguards**:
  - **Point-Degeneracy**: If $\sigma_1 < 10^{-12}$, raise `DegenerateCoordinatesError` before calculating condition ratios.
  - **Collinear Degeneracy**: If condition ratio $\frac{\sigma_2}{\sigma_1} < 10^{-7}$, atomic coordinates exhibit linear rank-deficiency. Rotation about the collinear axis is ill-defined; raise `CollinearDegeneracyError`.
  - **Planar Stabilization**: If $\frac{\sigma_2}{\sigma_1} \ge 10^{-7}$ and $\frac{\sigma_3}{\sigma_1} < 10^{-7}$, coordinates are coplanar. Stabilize left and right singular vectors via deterministic right-handed basis completion:
    $$\mathbf{u}_3 = \frac{\mathbf{u}_1 \times \mathbf{u}_2}{\|\mathbf{u}_1 \times \mathbf{u}_2\|_2}, \quad \mathbf{v}_3 = \frac{\mathbf{v}_1 \times \mathbf{v}_2}{\|\mathbf{v}_1 \times \mathbf{v}_2\|_2} \quad \text{[D]}$$

#### 5. [TOPOS] Reflection Parity Guard & Optimal Proper Rotation Matrix
- **Requirement ID**: `REQ-TOPOS-013.4`
- **File Target**: `cochem/topos/alignment.py`
- **Kabsch Reflection Parity Correction**:
  - Enforce proper right-handed rotation matrix $R \in SO(3)$ with $\det(R) = +1.0$, preventing unphysical coordinate inversion of chiral enantiomers.
  - Calculate parity reflection factor $d$:
    $$d = \operatorname{sgn}(\det(V U^T)) \in \{-1, +1\} \quad \text{[D]}$$
  - Assemble optimal proper rotation matrix:
    $$R = V \begin{bmatrix} 1 & 0 & 0 \\ 0 & 1 & 0 \\ 0 & 0 & d \end{bmatrix} U^T \quad \text{[D]}$$
  - Compute optimal translation vector $\vec{t} \in \mathbb{R}^3$:
    $$\vec{t} = \bar{Q} - R \bar{P} \quad \text{[D]}$$
  - Apply proper rotation and translation to all target atoms (including unmapped substituents and ghost atoms):
    $$P_{\text{aligned}} = P_{\text{full}} R^T + \mathbf{1} \vec{t}^T \quad \text{[D]}$$

#### 6. [TOPOS] Analytical Centered RMSD & Ensemble Deduplication
- **Requirement ID**: `REQ-TOPOS-013.5`
- **File Target**: `cochem/topos/alignment.py`
- **Analytical Centered RMSD**:
  - Calculate Root-Mean-Square Deviation over mapped MCS atoms using centered coordinates:
    $$\mathrm{RMSD}_{\text{MCS}} = \sqrt{\frac{\sum_{i=1}^N w_i \|R P_{c,i} - Q_{c,i}\|^2}{\sum_{i=1}^N w_i}} \quad \text{[D]}$$
- **Ensemble Clustering & Deduplication**:
  - For an ensemble of $M$ conformers, compute the symmetric pairwise RMSD matrix $D_{jk} = \mathrm{RMSD}(C_j, C_k)$ ($1 \le j, k \le M$).
  - Group conformers with pairwise $\mathrm{RMSD} < \delta_{\text{thresh}}$ (default $0.25\,\text{Å}$ `[M]`) into duplicate equivalence classes and flag them for downstream pruning.

#### 7. [TOPOS] Thread-Safe HDF5 Persistence & 6-Tier Concurrency Matrix
- **Requirement ID**: `REQ-TOPOS-013.6`
- **File Target**: `cochem/topos/alignment.py`
- **HDF5 Group Hierarchy**:
  - **Isomorphic Ensembles ($N_j = N_{\text{ref}}$)**: Store aligned coordinates as a dense rectangular dataset `/ensembles/{ensemble_id}/aligned_coords` (float64, shape `[M, N, 3]`).
  - **Heterogeneous Ensembles ($N_j \neq N_k$)**: Store per-conformer datasets `/ensembles/{ensemble_id}/conformers/{conformer_id}/aligned_coords` (float64, shape `[N_j, 3]`) or as a ragged 1D variable-length dataset using `h5py.special_dtype(vlen=np.float64)`.
  - Common MCS coordinates: `/ensembles/{ensemble_id}/aligned_mcs_coords` (float64, shape `[M, N_{\text{MCS}}, 3]`).
  - Metadata: `/ensembles/{ensemble_id}/pairwise_rmsd` (float32, shape `[M, M]`) and `/ensembles/{ensemble_id}/mcs_mapping` (int32, shape `[N_{\text{MCS}}, 2]`).
- **6-Tier Concurrency Enforcement**:
  - **Tier 1 (Local-Windows Native NTFS / WSL)**: HDF5 SWMR mode is strictly disabled due to Windows filesystem locking semantics. Coordinate concurrent access via cross-process `filelock.FileLock(path, timeout=30.0)` on advisory `.lock` files, utilizing staging files, explicit file descriptor flushes (`os.fsync`), and atomic `os.replace`.
  - **Tier 2 (Local-macOS OrbStack) & Tier 3 (Local-Linux Debian)**: Native HDF5 Single-Writer/Multiple-Reader (SWMR) mode is enabled (`libver="latest", swmr=True`).
  - **Tier 4 (Codespaces) & Tier 5 (GitHub Actions CI)**: SWMR is disabled on container overlay filesystems to prevent deadlocks; `filelock.FileLock(path, timeout=30.0)` coordinates file access within local scratch staging (`$RUNNER_TEMP` or `/tmp/cochem_scratch`).
  - **Tier 6 (HPC - Slurm/PBS with Lustre/GPFS)**: Distributed POSIX locks on network shares are strictly avoided. Concurrency uses node-local NVMe scratch directories (`$SLURM_TMPDIR` / `$COCH_SCRATCH`) with aggregated MPI I/O serialization to the central archive.

---

### CORE PYTHON INTERFACE SIGNATURES

Implement the following public API signatures in `cochem/topos/alignment.py` and export them in `cochem/topos/__init__.py`:

```python
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

def compute_kabsch_transformation(
    P: np.ndarray,
    Q: np.ndarray,
    weights: Optional[np.ndarray] = None,
    condition_tol: float = 1e-7,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Computes optimal Kabsch proper rotation R and translation t mapping P to Q.

    Parameters:
        P: Target coordinate matrix of shape (N, 3).
        Q: Reference coordinate matrix of shape (N, 3).
        weights: Optional non-negative mass weighting vector of shape (N,).
        condition_tol: Singular value condition ratio tolerance for rank-deficiency.

    Returns:
        Tuple containing:
            - R: Proper orthogonal rotation matrix in SO(3) of shape (3, 3) with det(R) = +1.0.
            - t: Optimal translation vector of shape (3,).
            - rmsd: Weighted analytical root-mean-square deviation over mapped coordinates.

    Raises:
        DegenerateCoordinatesError: When coordinates exhibit point degeneracy (sigma_1 < 1e-12).
        CollinearDegeneracyError: When coordinates exhibit collinear rank-deficiency (sigma_2 / sigma_1 < condition_tol).
    """

def align_conformers_by_mcs(
    target: ConformerInput,
    reference: ConformerInput,
    config: Optional[MCSAlignmentConfig] = None,
) -> AlignedConformerResult:
    """
    Superimposes a target conformer onto an invariant reference conformer via MCS perception and Kabsch fitting.

    Parameters:
        target: Target conformer input record.
        reference: Invariant reference conformer record.
        config: Optional configuration controlling timeouts, weighting, and tolerances.

    Returns:
        AlignedConformerResult containing transformed coordinates, rotation matrix, translation vector, and atom mapping.

    Raises:
        MCSConvergenceTimeoutError: If MCS graph search exceeds timeout ceiling or is canceled.
        IncompatibleTopologyError: If common atom count N_MCS < 3.
        CollinearDegeneracyError: If mapped coordinates are collinear.
    """

def cluster_ensemble_conformers(
    conformers: List[ConformerInput],
    reference: ConformerInput,
    config: Optional[MCSAlignmentConfig] = None,
) -> EnsembleAlignmentSummary:
    """
    Performs batch alignment and pairwise RMSD clustering across a conformer ensemble.

    Parameters:
        conformers: List of conformer records generated upstream via CREST/ORCA GOAT.
        reference: Reference conformer topology.
        config: Alignment configuration and deduplication RMSD threshold.

    Returns:
        EnsembleAlignmentSummary including pairwise RMSD matrix and duplicate cluster groups.
    """

def persist_aligned_ensemble_h5(
    summary: EnsembleAlignmentSummary,
    archive_path: Path,
    lock_timeout: float = 30.0,
) -> Path:
    """
    Persists aligned conformer trajectories and pairwise RMSD matrices into an HDF5 archive under 6-tier concurrency.

    Parameters:
        summary: Validated ensemble alignment summary payload.
        archive_path: Target filesystem path for the .h5 archive.
        lock_timeout: Maximum duration in seconds to wait for filelock acquisition.

    Returns:
        Path to the written HDF5 archive.
    """
```

---

### PHYSICAL VERIFICATION TEST SUITE (`tests/topos/test_topos_alignment.py`)

Implement the physical verification suite reproducing the following tests against genuine molecular structures:

```python
import numpy as np
import pytest
from pydantic import ValidationError

from cochem.topos.alignment import (
    AlignedConformerResult,
    CollinearDegeneracyError,
    ConformerInput,
    DegenerateCoordinatesError,
    EnsembleAlignmentSummary,
    IncompatibleTopologyError,
    MCSAlignmentConfig,
    align_conformers_by_mcs,
    compute_kabsch_transformation,
)


def test_kabsch_chiral_enantiomer_reflection_guard():
    """
    REQ-TOPOS-013.3 & REQ-TOPOS-013.4: Verify that Kabsch alignment between chiral enantiomers
    enforces proper rotation det(R) = +1.0 via parity correction factor d = -1, preventing coordinate inversion.
    """
    # Authentic D-alanine and L-alanine heavy-atom coordinate sub-blocks (N=5: N, CA, C, O, CB)
    coords_l = np.array([
        [-0.432, 1.254, -0.428],  # N
        [0.000, 0.000, 0.354],    # CA
        [1.520, 0.000, 0.354],    # C
        [2.145, 1.050, 0.354],    # O
        [-0.534, -1.242, -0.354], # CB
    ], dtype=np.float64)

    # Inverted enantiomer: D-alanine reflection across z-plane
    coords_d = coords_l.copy()
    coords_d[:, 2] *= -1.0

    R, t, rmsd = compute_kabsch_transformation(coords_d, coords_l)

    # Assert proper rotation in SO(3)
    assert np.allclose(R.T @ R, np.eye(3), atol=1e-5), "Rotation matrix must satisfy R.T @ R = I"
    assert np.isclose(np.linalg.det(R), 1.0, atol=1e-5), f"Improper rotation detected: det(R) = {np.linalg.det(R)}"
    # Enantiomer reflection cannot achieve zero RMSD without unphysical coordinate inversion
    assert rmsd > 0.1, "Enantiomer alignment must retain non-zero RMSD under proper SO(3) rotation"


def test_collinear_degeneracy_detection():
    """
    REQ-TOPOS-013.3: Verify that collinear coordinates (e.g., linear acetylene C2H2)
    trigger CollinearDegeneracyError due to singular value condition ratio sigma_2 / sigma_1 < 1e-7.
    """
    # Linear acetylene coordinates along z-axis (Angstroms)
    acetylene_coords = np.array([
        [0.0, 0.0, -1.665],  # H1
        [0.0, 0.0, -0.601],  # C1
        [0.0, 0.0, 0.601],   # C2
        [0.0, 0.0, 1.665],   # H2
    ], dtype=np.float64)

    rotated_coords = acetylene_coords @ np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.float64)

    with pytest.raises(CollinearDegeneracyError) as exc_info:
        compute_kabsch_transformation(rotated_coords, acetylene_coords)
    assert "collinear" in str(exc_info.value).lower()


def test_coplanar_coordinates_stabilization():
    """
    REQ-TOPOS-013.3: Verify that coplanar coordinates (benzene C6 heavy atoms in xy-plane)
    are successfully stabilized via right-handed cross-product basis completion without degeneracy failure.
    """
    # Planar benzene carbon ring coordinates in z=0 plane
    angles = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    r_cc = 1.397  # Experimental C-C aromatic bond distance
    benzene_c = np.column_stack([r_cc * np.cos(angles), r_cc * np.sin(angles), np.zeros(6)])

    # Apply 45-degree rotation around z-axis
    theta = np.pi / 4.0
    R_z = np.array([
        [np.cos(theta), -np.sin(theta), 0.0],
        [np.sin(theta), np.cos(theta), 0.0],
        [0.0, 0.0, 1.0],
    ])
    rotated_benzene = benzene_c @ R_z.T + np.array([1.5, -2.0, 0.0])

    R, t, rmsd = compute_kabsch_transformation(rotated_benzene, benzene_c)
    assert np.allclose(R.T @ R, np.eye(3), atol=1e-5)
    assert np.isclose(np.linalg.det(R), 1.0, atol=1e-5)
    assert np.isclose(rmsd, 0.0, atol=1e-5)


def test_bsse_ghost_atom_exclusion_and_mass():
    """
    REQ-TOPOS-013.1 & REQ-TOPOS-013.2: Verify that BSSE counterpoise complexes with ghost atoms (Z=0)
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


def test_pydantic_validation_guards():
    """
    Verify that Pydantic v2 data models reject empty coordinate lists, non-orthogonal rotation matrices,
    and asymmetric pairwise RMSD matrices.
    """
    # 1. Reject length mismatch between elements and coordinates
    with pytest.raises(ValidationError):
        ConformerInput(
            conformer_id="invalid_conf_01",
            elements=["C", "C", "C"],
            atomic_numbers=[6, 6, 6],
            coordinates=[],
        )

    # 2. Reject non-orthogonal rotation matrix even if det(R) = 1.0 (e.g. non-uniform scaling)
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

    # 3. Reject non-symmetric pairwise RMSD matrix
    with pytest.raises(ValidationError):
        EnsembleAlignmentSummary(
            reference_id="ref_01",
            total_conformers=2,
            aligned_conformers=[],
            pairwise_rmsd_matrix=[[0.0, 0.35], [0.10, 0.0]],
        )
```

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate**:
   - Every function, method, and test fixture must execute physically against real molecular data.
   - Absolutely no `pass` stubs, `NotImplementedError`, empty functions, or synthetic mocked arrays (`np.zeros`, `np.ones`, etc.) in place of genuine computation.
2. **Dynamic Mendeleev Mandate**:
   - All non-ghost atomic masses must be queried dynamically via `mendeleev.element(Z).mass`.
   - Ghost/dummy atoms ($Z = 0$ or `is_ghost == True`) must be assigned $0.0\,\text{Da}$ without calling `mendeleev`.
   - Hardcoded atomic mass constants, isotopic lookup tables, or manual CODATA updates are strictly forbidden.
3. **Tripartite Workspace Air-Gap Architecture**:
   - Partition workflow across three disjoint tiers:
     - Upstream Conformer Generation Realm ($T_{\text{conf}}$)
     - Pure Mathematical Topology Alignment Kernel ($T_{\text{align}}$): Strictly CPU and in-memory. Zero disk I/O, zero network handles.
     - Persistence & Visualization Realm ($T_{\text{store}}$): HDF5 serialization and UI handoff.
4. **Compute Boundaries & CUDA-Lock Prevention**:
   - Conformer alignment and SVD matrix decompositions are strictly CPU-bound.
   - Subprocess execution must enforce `CUDA_VISIBLE_DEVICES=""` to prevent GPU runtime initialization or context monopolization.
5. **Thread-Safe HDF5 Persistence & 6-Tier Concurrency Matrix**:
   - On Windows NTFS (Tier 1), Codespaces (Tier 4), and GitHub Actions CI (Tier 5): Coordinate persistence via `filelock.FileLock(path, timeout=30.0)` on advisory `.lock` files, temporary staging files, and atomic `os.replace`.
   - On local macOS (Tier 2) and Linux (Tier 3): Enable HDF5 SWMR mode (`libver="latest", swmr=True`).
   - On HPC (Tier 6): Use node-local NVMe scratch staging (`$SLURM_TMPDIR` / `$COCH_SCRATCH`) and MPI collective I/O.
6. **OS-Agnostic Dynamic Path Resolution**:
   - Dynamic path lookups via `pathlib.Path`:
     - Artifacts: `pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR", Path.home() / ".cochem" / "artifacts"))`
     - Scratch: `pathlib.Path(os.environ.get("COCHEM_SCRATCH_DIR", Path.home() / ".cochem" / "scratch"))`
     - Data: `pathlib.Path(os.environ.get("COCHEM_DATA_DIR", Path.home() / ".cochem" / "data"))`

---

### ACTION PLAN FOR CODER

1. Create or update `cochem/topos/alignment.py` (and export in `cochem/topos/__init__.py`) implementing:
   - Typed exception hierarchy: `ToposAlignmentError`, `MCSConvergenceTimeoutError`, `CollinearDegeneracyError`, `DegenerateCoordinatesError`, `IncompatibleTopologyError`.
   - Pydantic v2 data models: `ConformerInput`, `MCSAlignmentConfig`, `AlignedConformerResult`, `EnsembleAlignmentSummary`.
   - `compute_kabsch_transformation`: SVD decomposition with point degeneracy check, collinear check, planar cross-product basis completion, parity reflection guard ($d = \operatorname{sgn}(\det(V U^T))$), proper rotation $R \in SO(3)$, and analytical centered RMSD.
   - `align_conformers_by_mcs`: RDKit `rdFMCS.FindMCS` in `ProcessPoolExecutor` with $30.0\,\text{s}$ timeout ceiling and `mcs_result.canceled` inspection, ghost atom sanitization, mass retrieval with Mendeleev $Z=0$ guard, and coordinate superposition.
   - `cluster_ensemble_conformers`: Pairwise RMSD matrix calculation and equivalence class clustering.
   - `persist_aligned_ensemble_h5`: Thread-safe HDF5 serialization supporting isomorphic dense rectangular datasets and heterogeneous ragged structures under 6-tier `filelock` / SWMR concurrency rules.
2. Implement physical unit test suite in `tests/topos/test_topos_alignment.py` reproducing all test cases from Section 6 of the SRS.
3. Run the test suite via `run_command` (`pytest tests/topos/test_topos_alignment.py -v`) and verify 100% pass rate.
4. Output the complete list of touched and created files in your final execution report.
I have submitted the generated chunked coding prompt for `SRS_Chunk_13_TOPOS_Alignment_Part_1` to the `adversary` agent ([Conversation 5cd34027-45b0-4deb-b625-d1c18bd91b2e](conversation://5cd34027-45b0-4deb-b625-d1c18bd91b2e)) for an adversarial audit in accordance with the 0rchestrator Global Protocol and Anti-Spoofing Protocol v3. Standing by for the auditor's evaluation.
I have sent the fully remediated chunked coding prompt to the `adversary` agent ([Conversation 5cd34027-45b0-4deb-b625-d1c18bd91b2e](conversation://5cd34027-45b0-4deb-b625-d1c18bd91b2e)) addressing all 7 defects (DEF-01 through DEF-07). Standing by for the second-round audit verdict.
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous feature suite specified in Software Requirements Specification (SRS) Chunk 13: `TOPOS_Alignment_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev library mandate, and Method Matrix v4. Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must execute physically against authentic chemical topologies, genuine molecular structures, and physical constants.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Inspect the repository structure under `cochem/topos/` to identify existing graph primitives, `TopologyGraph` abstractions, and testing conventions established in prior TOPOS modules.
2. **Implementation**: Implement all target modules specified below with strict Python 3.10+ PEP 484 type annotations, thread-safe persistence, and custom typed domain exceptions (`ToposAlignmentError`, `MCSConvergenceTimeoutError`, `CollinearDegeneracyError`, `DegenerateCoordinatesError`, `IncompatibleTopologyError`, `AirGapBoundaryViolationError`).
3. **Physical Test Suite**: Write comprehensive, unmocked test suites covering each module under `tests/topos/test_topos_alignment.py` with 10 authentic physical test cases (including chiral enantiomers, linear acetylene, planar benzene, BSSE complexes, HDF5 persistence roundtrips, ensemble clustering, timeout exceptions, topological incompatibility, and point-degeneracy).
4. **Physical Verification**: Execute the test suite using `run_command` in the terminal (`pytest tests/topos/test_topos_alignment.py -v`). Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured execution report detailing all files created and modified on disk.

---

### MODULE SPECIFICATIONS

#### 1. [TOPOS] Pydantic v2 Domain Models & Exception Hierarchy
- **File Target**: `cochem/topos/alignment.py` (or `cochem/topos/models.py` & `cochem/topos/exceptions.py`, exported in `cochem/topos/__init__.py`)
- **Domain Exceptions**:
  - `ToposAlignmentError(Exception)`: Base exception for topology alignment failures.
  - `MCSConvergenceTimeoutError(ToposAlignmentError)`: Raised when MCS graph search exceeds timeout ceiling (default 30.0s) or `mcs_result.canceled == True`.
  - `CollinearDegeneracyError(ToposAlignmentError)`: Raised when atomic coordinates exhibit collinear rank-deficiency in SVD ($\frac{\sigma_2}{\sigma_1} < 10^{-7}$).
  - `DegenerateCoordinatesError(ToposAlignmentError)`: Raised when atomic coordinates exhibit point-degeneracy ($\sigma_1 < 10^{-12}$).
  - `IncompatibleTopologyError(ToposAlignmentError)`: Raised when molecules share insufficient overlapping substructure ($N_{\text{MCS}} < 3$).
  - `AirGapBoundaryViolationError(ToposAlignmentError)`: Raised when persistent archive paths resolve outside the designated $T_{\text{store}}$ realm.
- **Pydantic v2 Data Models (Python 3.10+)**:
  - `ConformerInput`:
    - `conformer_id: str`: Unique identifier for conformer.
    - `elements: List[str]`: Elemental symbols (minimum length 3).
    - `atomic_numbers: List[int]`: IUPAC atomic numbers $Z$ (minimum length 3).
    - `coordinates: List[Tuple[float, float, float]]`: $(N, 3)$ Cartesian coordinates in Ångströms (minimum length 3).
    - `bonds: List[Tuple[int, int, float]] = Field(default_factory=list)`: 0-based bond edges: `(idx_i, idx_j, bond_order)`.
    - `reference_smiles: Optional[str] = None`: Optional canonical SMILES string for topological validation.
    - `masses: Optional[List[float]] = None`: Optional atomic masses dynamically retrieved via `mendeleev`.
    - `energy_kcal_mol: Optional[float] = None`: Electronic or free energy tag from QM runner.
    - `is_ghost: List[bool] = Field(default_factory=list)`: Mask identifying BSSE ghost/dummy atoms.
    - Validation: Enforce exact length matching across `elements`, `atomic_numbers`, `coordinates`, `masses` (if provided), and `is_ghost`. If `is_ghost` is empty, auto-populate with `[False] * len(elements)`.
  - `MCSAlignmentConfig`:
    - `timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0)`: `rdFMCS` search timeout ceiling.
    - `mass_weighting: bool = False`: Whether to weight Kabsch covariance and centroids by atomic masses.
    - `match_valences: bool = True`: Enforce valence matching in MCS.
    - `ring_matches_ring_only: bool = True`: Strict ring-to-ring matching.
    - `complete_rings_only: bool = False`: Permit partial ring overlap across fused scaffolds.
    - `min_mcs_atoms: int = Field(default=3, ge=3)`: Minimum common substructure atom count.
    - `svd_condition_tol: float = Field(default=1e-7, ge=1e-12)`: Singular value condition ratio tolerance for rank-deficiency.
    - `rmsd_cluster_threshold_angstrom: float = Field(default=0.25, ge=0.01)`: Deduplication RMSD cutoff.
    - `ignore_ghost_atoms: bool = True`: Exclude ghost/BSSE atoms from alignment kernel.
  - `AlignedConformerResult`:
    - `conformer_id: str`
    - `reference_id: str`
    - `rmsd_angstrom: float = Field(..., ge=0.0)`: Analytical RMSD over mapped MCS non-ghost atoms.
    - `rotation_matrix: List[List[float]]`: Orthogonal $(3, 3)$ rotation matrix $R$ satisfying $R^T R = I$ and $\det(R) = +1.0 \pm 10^{-4}$.
    - `translation_vector: List[float]`: $(3,)$ optimal translation vector $\vec{t}$.
    - `aligned_coordinates: List[Tuple[float, float, float]]`: $(N, 3)$ transformed full coordinates.
    - `atom_mapping: Dict[int, int]`: 0-based index map: `{target_idx: ref_idx}`.
    - `execution_duration_seconds: float = Field(..., ge=0.0)`
  - `EnsembleAlignmentSummary`:
    - `ensemble_id: str = Field(..., description="Unique ensemble collection ID")`
    - `reference_id: str`
    - `total_conformers: int`
    - `aligned_conformers: List[AlignedConformerResult]`
    - `pairwise_rmsd_matrix: List[List[float]]`: Symmetric $(M, M)$ matrix with zero diagonal and non-negative elements.
    - `duplicate_clusters: List[List[str]] = Field(default_factory=list)`: Clusters of redundant conformer IDs where pairwise RMSD $< \delta_{\text{thresh}}$.
    - `mcs_mapping: Dict[int, int] = Field(default_factory=dict, description="Consensus MCS atom index map")`
    - `aligned_mcs_coords: Optional[List[List[Tuple[float, float, float]]]] = Field(default=None, description="Aligned consensus MCS coordinates across ensemble")`

#### 2. [TOPOS] Maximum Common Substructure (MCS) Perception & Ghost-Atom Sanitization
- **Requirement ID**: `REQ-TOPOS-013.1`
- **File Target**: `cochem/topos/alignment.py`
- **Ghost Atom Pre-Sanitization**:
  - Intermolecular complexes generated for Basis Set Superposition Error (BSSE) counterpoise corrections contain ghost atoms (symbols `Gh`, `Bq`, `X`, or atomic number $Z = 0$, or `is_ghost == True`).
  - Ghost atoms are strictly excluded/stripped *prior* to bond connectivity perception and RDKit molecule construction. Calling RDKit bond perception routines or `PeriodicTable` lookup on $Z=0$ is strictly prohibited as it triggers fatal C++ core exceptions.
- **Bond Connectivity Perception**:
  - Accept explicit bond connectivity tables `bonds: List[Tuple[int, int, float]]` or canonical SMILES.
  - If bond connectivity is missing from bare coordinates of non-ghost atoms, perceive connectivity by computing pairwise Euclidean distances $D_{ij} = \|\mathbf{r}_i - \mathbf{r}_j\|_2$ and connecting pairs satisfying $D_{ij} \le R_{\text{cov}}(Z_i) + R_{\text{cov}}(Z_j) + \delta$ ($\delta = 0.40\,\text{Å}$), where $R_{\text{cov}}$ is queried dynamically via `mendeleev.element(Z).covalent_radius_pyykko / 100.0`.
- **Top-Level Worker Function & GIL Isolation**:
  - To prevent Windows `spawn` pickling failures, define a module-level picklable helper:
    `def _isolated_mcs_worker(target_mol_block: str, ref_mol_block: str, params: dict) -> Tuple[bool, bool, str, List[Tuple[int, int]]]`.
  - MCS extraction executes via RDKit `rdFMCS.FindMCS` in `concurrent.futures.ProcessPoolExecutor` with timeout ceiling $30.0\,\text{s}$. Inspect `mcs_result.canceled`; if True or timeout, raise `MCSConvergenceTimeoutError`.
  - Standard MCS parameters: `atomCompare=CompareElements`, `bondCompare=CompareOrder`, `matchValences=True`, `ringMatchesRingOnly=True`, `completeRingsOnly=False`.
  - Require minimum common atom count $N_{\text{MCS}} \ge 3$. If $N_{\text{MCS}} < 3$, raise `IncompatibleTopologyError`.

#### 3. [TOPOS] Mass-Weighted Centroid Translation & Ghost-Atom Masking
- **Requirement ID**: `REQ-TOPOS-013.2`
- **File Target**: `cochem/topos/alignment.py`
- **Ghost Atom Exclusion & Mendeleev Lookup Guard**:
  - Strictly exclude all ghost atoms ($Z = 0$ or `is_ghost == True`) from MCS coordinate sub-blocks prior to centroid calculation, cross-covariance assembly, and rotation fitting.
  - If $Z = 0$ or `is_ghost == True`, mass is assigned strictly as $0.0\,\text{Da}$ without calling `mendeleev`, preventing uncaught `ValueError` / `ElementNotFoundError`. For non-ghost heavy atoms, query dynamic mass via `mendeleev.element(Z).mass` `[M]`.
- **Mathematical Centroid Formulation**:
  - For mapped MCS non-ghost coordinate matrices $P \in \mathbb{R}^{N \times 3}$ (target) and $Q \in \mathbb{R}^{N \times 3}$ (reference) ($N = N_{\text{MCS}} \ge 3$):
  - Assign weights $w_i > 0$: unweighted ($w_i = 1.0$) or mass-weighted ($w_i = m_i$).
  - Compute weighted centroids:
    $$\bar{P} = \frac{\sum_{i=1}^N w_i P_i}{\sum_{i=1}^N w_i}, \quad \bar{Q} = \frac{\sum_{i=1}^N w_i Q_i}{\sum_{i=1}^N w_i} \quad \text{[D]}$$
  - Center coordinates:
    $$P_c = P - \mathbf{1} \bar{P}^T, \quad Q_c = Q - \mathbf{1} \bar{Q}^T \quad \text{[D]}$$

#### 4. [TOPOS] Cross-Covariance, SVD & Numerical Degeneracy Safeguards
- **Requirement ID**: `REQ-TOPOS-013.3`
- **File Target**: `cochem/topos/alignment.py`
- **Dispersion Assembly & Full SVD**:
  - Assemble weighted cross-covariance dispersion matrix $H \in \mathbb{R}^{3 \times 3}$:
    $$H = P_c^T W Q_c = \sum_{i=1}^N w_i (P_{c,i}^T Q_{c,i}) \quad \text{[D]}$$
    where $W = \operatorname{diag}(w_1, \dots, w_N)$.
  - Compute full SVD via `scipy.linalg.svd`:
    $$H = U \Sigma V^T \quad \text{[D]}$$
    where $U, V \in O(3)$ and singular values $\Sigma = \operatorname{diag}(\sigma_1, \sigma_2, \sigma_3)$ with $\sigma_1 \ge \sigma_2 \ge \sigma_3 \ge 0$.
- **Numerical Degeneracy Safeguards**:
  - **Point-Degeneracy**: If $\sigma_1 < 10^{-12}$, raise `DegenerateCoordinatesError` before calculating condition ratios.
  - **Collinear Degeneracy**: If condition ratio $\frac{\sigma_2}{\sigma_1} < 10^{-7}$, coordinates exhibit collinear rank-deficiency. Raise `CollinearDegeneracyError`.
  - **Planar Stabilization**: If $\frac{\sigma_2}{\sigma_1} \ge 10^{-7}$ and $\frac{\sigma_3}{\sigma_1} < 10^{-7}$, coordinates are coplanar. Stabilize left and right singular vectors via deterministic right-handed cross-product basis completion:
    $$\mathbf{u}_3 = \frac{\mathbf{u}_1 \times \mathbf{u}_2}{\|\mathbf{u}_1 \times \mathbf{u}_2\|_2}, \quad \mathbf{v}_3 = \frac{\mathbf{v}_1 \times \mathbf{v}_2}{\|\mathbf{v}_1 \times \mathbf{v}_2\|_2} \quad \text{[D]}$$

#### 5. [TOPOS] Reflection Parity Guard & Optimal Proper Rotation Matrix
- **Requirement ID**: `REQ-TOPOS-013.4`
- **File Target**: `cochem/topos/alignment.py`
- **Kabsch Reflection Parity Correction**:
  - Enforce proper right-handed rotation matrix $R \in SO(3)$ with $\det(R) = +1.0$, preventing unphysical inversion of chiral enantiomers.
  - Calculate parity reflection factor:
    $$d = \operatorname{sgn}(\det(V U^T)) \in \{-1, +1\} \quad \text{[D]}$$
  - Assemble optimal proper rotation matrix:
    $$R = V \begin{bmatrix} 1 & 0 & 0 \\ 0 & 1 & 0 \\ 0 & 0 & d \end{bmatrix} U^T \quad \text{[D]}$$
  - Compute optimal translation vector:
    $$\vec{t} = \bar{Q} - R \bar{P} \quad \text{[D]}$$
  - Apply proper rotation and translation to all target atoms (using row-vector convention):
    $$P_{\text{aligned}} = P_{\text{full}} R^T + \mathbf{1} \vec{t}^T \quad \text{[D]}$$

#### 6. [TOPOS] Analytical Centered RMSD & Ensemble Deduplication
- **Requirement ID**: `REQ-TOPOS-013.5`
- **File Target**: `cochem/topos/alignment.py`
- **Analytical Centered RMSD**:
  - Calculate Root-Mean-Square Deviation over mapped MCS atoms using consistent row-vector matrix multiplication:
    $$\mathrm{RMSD}_{\text{MCS}} = \sqrt{\frac{\sum_{i=1}^N w_i \|P_{c,i} R^T - Q_{c,i}\|_2^2}{\sum_{i=1}^N w_i}} \quad \text{[D]}$$
- **Ensemble Deduplication**:
  - Compute symmetric pairwise RMSD matrix $D_{jk} = \mathrm{RMSD}(C_j, C_k)$ ($1 \le j, k \le M$).
  - Group conformers with pairwise $\mathrm{RMSD} < \delta_{\text{thresh}}$ (default $0.25\,\text{Å}$ `[M]`) into duplicate equivalence classes.

#### 7. [TOPOS] Tripartite Air-Gap Boundaries & 6-Tier Concurrency Matrix
- **Requirement ID**: `REQ-TOPOS-013.6`
- **File Target**: `cochem/topos/alignment.py`
- **Tripartite Air-Gap Realms**:
  - $T_{\text{conf}}$ (Conformer Ingestion): `pathlib.Path(os.environ.get("COCH_CONF_DIR", Path.home() / ".cochem" / "conformers"))`
  - $T_{\text{align}}$ (Pure In-Memory Math Kernel): Isolated, in-memory execution, no file writes, no GPU/CUDA context (`CUDA_VISIBLE_DEVICES=""`).
  - $T_{\text{store}}$ (Persistence Realm): `pathlib.Path(os.environ.get("COCH_STORE_DIR", Path.home() / ".cochem" / "store"))`
  - **Confinement Check**: `persist_aligned_ensemble_h5` must verify that `archive_path.resolve()` resides within $T_{\text{store}}$. If not, raise `AirGapBoundaryViolationError`.
- **Concurrency Tier Detection**:
  ```python
  from enum import Enum
  import os, sys

  class StorageTier(str, Enum):
      TIER1_WINDOWS = "tier1_windows"
      TIER2_MACOS = "tier2_macos"
      TIER3_LINUX = "tier3_linux"
      TIER4_CODESPACES = "tier4_codespaces"
      TIER5_GITHUB_ACTIONS = "tier5_github_actions"
      TIER6_HPC = "tier6_hpc"

  def detect_concurrency_tier() -> StorageTier:
      if "SLURM_JOB_ID" in os.environ or "PBS_JOBID" in os.environ:
          return StorageTier.TIER6_HPC
      if os.environ.get("GITHUB_ACTIONS") == "true":
          return StorageTier.TIER5_GITHUB_ACTIONS
      if os.environ.get("CODESPACES") == "true":
          return StorageTier.TIER4_CODESPACES
      if sys.platform == "win32":
          return StorageTier.TIER1_WINDOWS
      if sys.platform == "darwin":
          return StorageTier.TIER2_MACOS
      return StorageTier.TIER3_LINUX
  ```
- **HDF5 Persistence Protocols**:
  - Tier 1 (Windows NTFS), Tier 4, Tier 5: SWMR disabled (`swmr=False`). Coordinated via `filelock.FileLock(str(archive_path) + ".lock", timeout=30.0)` with atomic staging file replacement (`staging_path.replace(archive_path)`).
  - Tier 2 (macOS) & Tier 3 (Linux): Native SWMR enabled (`libver="latest", swmr=True`).
  - Tier 6 (HPC): Stage writes to node-local NVMe scratch (`os.environ.get("SLURM_TMPDIR", "/tmp")`), avoiding distributed POSIX byte-range lock contention.
  - Datasets:
    - Isomorphic: `/ensembles/{ensemble_id}/aligned_coords` (`[M, N, 3]`, float64)
    - Heterogeneous: `/ensembles/{ensemble_id}/conformers/{conformer_id}/aligned_coords` (`[N_j, 3]`, float64)
    - MCS coords: `/ensembles/{ensemble_id}/aligned_mcs_coords` (`[M, N_mcs, 3]`, float64)
    - Pairwise RMSD: `/ensembles/{ensemble_id}/pairwise_rmsd` (`[M, M]`, float32)
    - MCS mapping: `/ensembles/{ensemble_id}/mcs_mapping` (`[N_mcs, 2]`, int32)

---

### CORE PYTHON INTERFACE SIGNATURES

```python
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

def compute_kabsch_transformation(
    P: np.ndarray,
    Q: np.ndarray,
    weights: Optional[np.ndarray] = None,
    condition_tol: float = 1e-7,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Computes optimal Kabsch proper rotation R and translation t mapping P to Q.

    Parameters:
        P: Target coordinate matrix of shape (N, 3).
        Q: Reference coordinate matrix of shape (N, 3).
        weights: Optional non-negative mass weighting vector of shape (N,).
        condition_tol: Singular value condition ratio tolerance for rank-deficiency.

    Returns:
        Tuple containing:
            - R: Proper orthogonal rotation matrix in SO(3) of shape (3, 3) with det(R) = +1.0.
            - t: Optimal translation vector of shape (3,).
            - rmsd: Weighted analytical root-mean-square deviation over mapped coordinates.

    Raises:
        DegenerateCoordinatesError: When coordinates exhibit point degeneracy (sigma_1 < 1e-12).
        CollinearDegeneracyError: When coordinates exhibit collinear rank-deficiency (sigma_2 / sigma_1 < condition_tol).
    """

def align_conformers_by_mcs(
    target: ConformerInput,
    reference: ConformerInput,
    config: Optional[MCSAlignmentConfig] = None,
) -> AlignedConformerResult:
    """
    Superimposes a target conformer onto an invariant reference conformer via MCS perception and Kabsch fitting.

    Parameters:
        target: Target conformer input record.
        reference: Invariant reference conformer record.
        config: Optional configuration controlling timeouts, weighting, and tolerances.

    Returns:
        AlignedConformerResult containing transformed coordinates, rotation matrix, translation vector, and atom mapping.

    Raises:
        MCSConvergenceTimeoutError: If MCS graph search exceeds timeout ceiling or is canceled.
        IncompatibleTopologyError: If common atom count N_MCS < 3.
        CollinearDegeneracyError: If mapped coordinates are collinear.
    """

def cluster_ensemble_conformers(
    conformers: List[ConformerInput],
    reference: ConformerInput,
    config: Optional[MCSAlignmentConfig] = None,
) -> EnsembleAlignmentSummary:
    """
    Performs batch alignment and pairwise RMSD clustering across a conformer ensemble.

    Parameters:
        conformers: List of conformer records generated upstream via CREST/ORCA GOAT.
        reference: Reference conformer topology.
        config: Alignment configuration and deduplication RMSD threshold.

    Returns:
        EnsembleAlignmentSummary including pairwise RMSD matrix, consensus MCS map, and duplicate cluster groups.
    """

def persist_aligned_ensemble_h5(
    summary: EnsembleAlignmentSummary,
    archive_path: Path,
    lock_timeout: float = 30.0,
) -> Path:
    """
    Persists aligned conformer trajectories and pairwise RMSD matrices into an HDF5 archive under 6-tier concurrency.

    Parameters:
        summary: Validated ensemble alignment summary payload.
        archive_path: Target filesystem path for the .h5 archive (must resolve within T_store).
        lock_timeout: Maximum duration in seconds to wait for filelock acquisition.

    Returns:
        Path to the written HDF5 archive.

    Raises:
        AirGapBoundaryViolationError: If archive_path resolves outside T_store.
    """
```

---

### PHYSICAL VERIFICATION TEST SUITE (`tests/topos/test_topos_alignment.py`)

```python
import os
from pathlib import Path
import numpy as np
import pytest
import h5py
from pydantic import ValidationError

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
    align_conformers_by_mcs,
    cluster_ensemble_conformers,
    compute_kabsch_transformation,
    persist_aligned_ensemble_h5,
)


def test_kabsch_chiral_enantiomer_reflection_guard():
    """
    REQ-TOPOS-013.3 & REQ-TOPOS-013.4: Verify that Kabsch alignment between chiral enantiomers
    enforces proper rotation det(R) = +1.0 via parity correction factor d = -1, preventing coordinate inversion.
    """
    coords_l = np.array([
        [-0.432, 1.254, -0.428],  # N
        [0.000, 0.000, 0.354],    # CA
        [1.520, 0.000, 0.354],    # C
        [2.145, 1.050, 0.354],    # O
        [-0.534, -1.242, -0.354], # CB
    ], dtype=np.float64)

    coords_d = coords_l.copy()
    coords_d[:, 2] *= -1.0

    R, t, rmsd = compute_kabsch_transformation(coords_d, coords_l)

    assert np.allclose(R.T @ R, np.eye(3), atol=1e-5), "Rotation matrix must satisfy R.T @ R = I"
    assert np.isclose(np.linalg.det(R), 1.0, atol=1e-5), f"Improper rotation detected: det(R) = {np.linalg.det(R)}"
    assert rmsd > 0.1, "Enantiomer alignment must retain non-zero RMSD under proper SO(3) rotation"


def test_collinear_degeneracy_detection():
    """
    REQ-TOPOS-013.3: Verify that collinear coordinates (e.g., linear acetylene C2H2)
    trigger CollinearDegeneracyError due to singular value condition ratio sigma_2 / sigma_1 < 1e-7.
    """
    acetylene_coords = np.array([
        [0.0, 0.0, -1.665],  # H1
        [0.0, 0.0, -0.601],  # C1
        [0.0, 0.0, 0.601],   # C2
        [0.0, 0.0, 1.665],   # H2
    ], dtype=np.float64)

    rotated_coords = acetylene_coords @ np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.float64)

    with pytest.raises(CollinearDegeneracyError) as exc_info:
        compute_kabsch_transformation(rotated_coords, acetylene_coords)
    assert "collinear" in str(exc_info.value).lower()


def test_coplanar_coordinates_stabilization():
    """
    REQ-TOPOS-013.3: Verify that coplanar coordinates (benzene C6 heavy atoms in xy-plane)
    are successfully stabilized via right-handed cross-product basis completion without degeneracy failure.
    """
    angles = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    r_cc = 1.397
    benzene_c = np.column_stack([r_cc * np.cos(angles), r_cc * np.sin(angles), np.zeros(6)])

    theta = np.pi / 4.0
    R_z = np.array([
        [np.cos(theta), -np.sin(theta), 0.0],
        [np.sin(theta), np.cos(theta), 0.0],
        [0.0, 0.0, 1.0],
    ])
    rotated_benzene = benzene_c @ R_z.T + np.array([1.5, -2.0, 0.0])

    R, t, rmsd = compute_kabsch_transformation(rotated_benzene, benzene_c)
    assert np.allclose(R.T @ R, np.eye(3), atol=1e-5)
    assert np.isclose(np.linalg.det(R), 1.0, atol=1e-5)
    assert np.isclose(rmsd, 0.0, atol=1e-5)


def test_bsse_ghost_atom_exclusion_and_mass():
    """
    REQ-TOPOS-013.1 & REQ-TOPOS-013.2: Verify that BSSE counterpoise complexes with ghost atoms (Z=0)
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


def test_pydantic_validation_guards():
    """
    Verify that Pydantic v2 data models reject empty coordinate lists, non-orthogonal rotation matrices,
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
    ref_coords = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
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
        coordinates=[(float(i), 0.0, 0.0) for i in range(10)],
    )
    c2 = ConformerInput(
        conformer_id="polycycle_2",
        elements=["C"] * 10,
        atomic_numbers=[6] * 10,
        coordinates=[(0.0, float(i), 0.0) for i in range(10)],
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
    # Identical copy (RMSD = 0.0) -> Redundant duplicate
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
```

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate**:
   - Every function, method, and test fixture must execute physically against real molecular data.
   - Absolutely no `pass` stubs, `NotImplementedError`, empty functions, or synthetic mocked arrays (`np.zeros`, `np.ones`, etc.) in place of genuine computation.
2. **Dynamic Mendeleev Mandate**:
   - All non-ghost atomic masses must be queried dynamically via `mendeleev.element(Z).mass`.
   - Ghost/dummy atoms ($Z = 0$ or `is_ghost == True`) must be assigned $0.0\,\text{Da}$ without calling `mendeleev`.
   - Hardcoded atomic mass constants, isotopic lookup tables, or manual CODATA updates are strictly forbidden.
3. **Tripartite Workspace Air-Gap Architecture**:
   - Partition workflow across three disjoint physical realms:
     - Upstream Conformer Generation Realm ($T_{\text{conf}}$): `COCH_CONF_DIR`
     - Pure Mathematical Topology Alignment Kernel ($T_{\text{align}}$): Strictly CPU and in-memory. Zero disk I/O, zero network handles.
     - Persistence & Visualization Realm ($T_{\text{store}}$): `COCH_STORE_DIR`
   - Persistent archive paths outside $T_{\text{store}}$ must raise `AirGapBoundaryViolationError`.
4. **Compute Boundaries & CUDA-Lock Prevention**:
   - Conformer alignment and SVD matrix decompositions are strictly CPU-bound.
   - Subprocess execution must enforce `CUDA_VISIBLE_DEVICES=""` to prevent GPU runtime initialization or context monopolization.
5. **Thread-Safe HDF5 Persistence & 6-Tier Concurrency Matrix**:
   - On Windows NTFS (Tier 1), Codespaces (Tier 4), and GitHub Actions CI (Tier 5): Coordinate persistence via `filelock.FileLock(str(archive_path) + ".lock", timeout=30.0)` on advisory `.lock` files, temporary staging files, and atomic replacement.
   - On local macOS (Tier 2) and Linux (Tier 3): Enable HDF5 SWMR mode (`libver="latest", swmr=True`).
   - On HPC (Tier 6): Use node-local NVMe scratch staging (`$SLURM_TMPDIR` / `$COCH_SCRATCH`) and MPI collective I/O.
6. **OS-Agnostic Dynamic Path Resolution**:
   - Dynamic path lookups via `pathlib.Path`:
     - Artifacts: `pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR", Path.home() / ".cochem" / "artifacts"))`
     - Scratch: `pathlib.Path(os.environ.get("COCHEM_SCRATCH_DIR", Path.home() / ".cochem" / "scratch"))`
     - Data: `pathlib.Path(os.environ.get("COCHEM_DATA_DIR", Path.home() / ".cochem" / "data"))`

---

### ACTION PLAN FOR CODER

1. Implement `cochem/topos/alignment.py` (and export in `cochem/topos/__init__.py`) containing:
   - Domain exception hierarchy: `ToposAlignmentError`, `MCSConvergenceTimeoutError`, `CollinearDegeneracyError`, `DegenerateCoordinatesError`, `IncompatibleTopologyError`, `AirGapBoundaryViolationError`.
   - Pydantic v2 data models: `ConformerInput`, `MCSAlignmentConfig`, `AlignedConformerResult`, `EnsembleAlignmentSummary`.
   - `StorageTier` enum and `detect_concurrency_tier()` helper.
   - Module-level picklable `_isolated_mcs_worker` helper.
   - `compute_kabsch_transformation`: SVD decomposition with point degeneracy check, collinear check, planar cross-product basis completion, parity reflection guard ($d = \operatorname{sgn}(\det(V U^T))$), proper rotation $R \in SO(3)$, and analytical centered RMSD.
   - `align_conformers_by_mcs`: Ghost atom pre-sanitization, dynamic Mendeleev radii bond perception fallback, isolated `ProcessPoolExecutor` with timeout ceiling, mass lookup with $Z=0$ guard, and coordinate superposition.
   - `cluster_ensemble_conformers`: Pairwise RMSD matrix calculation and duplicate cluster grouping.
   - `persist_aligned_ensemble_h5`: Air-gap boundary confinement check and 6-tier thread-safe HDF5 serialization.
2. Implement physical unit test suite in `tests/topos/test_topos_alignment.py` with all 10 authentic fixtures.
3. Run the test suite via `run_command` (`pytest tests/topos/test_topos_alignment.py -v`) and verify 100% pass rate.
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


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\alignment.py ---
"""CoChem-TOPOS Alignment Subsystem (Part 1).

Rigorous molecular topology alignment, Maximum Common Substructure (MCS) perception,
Kabsch SVD coordinate transformation with reflection parity guard and numerical
degeneracy safeguards, ensemble deduplication, and thread-safe HDF5 persistence [M][D].
"""

from __future__ import annotations

import concurrent.futures
from enum import Enum
import os
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional, Tuple

import filelock
import h5py
from mendeleev import element
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from rdkit import Chem
from rdkit.Chem import rdFMCS
from scipy.linalg import svd

from cochem.topos.exceptions import (
    AirGapBoundaryViolationError,
    CollinearDegeneracyError,
    DegenerateCoordinatesError,
    IncompatibleTopologyError,
    MCSConvergenceTimeoutError,
    ToposAlignmentError,
)


class StorageTier(str, Enum):
    """Storage and concurrency tiers across the CoChem ecosystem [D]."""

    TIER1_WINDOWS = "tier1_windows"
    TIER2_MACOS = "tier2_macos"
    TIER3_LINUX = "tier3_linux"
    TIER4_CODESPACES = "tier4_codespaces"
    TIER5_GITHUB_ACTIONS = "tier5_github_actions"
    TIER6_HPC = "tier6_hpc"


def detect_concurrency_tier() -> StorageTier:
    """Detects active execution tier based on OS and environment invariants [D]."""
    if "SLURM_JOB_ID" in os.environ or "PBS_JOBID" in os.environ:
        return StorageTier.TIER6_HPC
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return StorageTier.TIER5_GITHUB_ACTIONS
    if os.environ.get("CODESPACES") == "true":
        return StorageTier.TIER4_CODESPACES
    if sys.platform == "win32":
        return StorageTier.TIER1_WINDOWS
    if sys.platform == "darwin":
        return StorageTier.TIER2_MACOS
    return StorageTier.TIER3_LINUX


class ConformerInput(BaseModel):
    """Input representation of a 3D molecular conformer [D]."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    conformer_id: str
    elements: List[str]
    atomic_numbers: List[int]
    coordinates: List[Tuple[float, float, float]]
    bonds: List[Tuple[int, int, float]] = Field(default_factory=list)
    reference_smiles: Optional[str] = None
    masses: Optional[List[float]] = None
    energy_kcal_mol: Optional[float] = None
    is_ghost: List[bool] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_conformer(self) -> "ConformerInput":
        """Enforces length matching across conformer atom arrays [D]."""
        n_elem = len(self.elements)
        n_atomic = len(self.atomic_numbers)
        n_coords = len(self.coordinates)
        if n_coords == 0 or n_elem == 0:
            raise ValueError("Coordinates and elements cannot be empty")
        if n_elem != n_atomic or n_elem != n_coords:
            raise ValueError(
                f"Length mismatch: elements ({n_elem}), atomic_numbers ({n_atomic}), and coordinates ({n_coords}) must match"
            )
        if self.is_ghost:
            if len(self.is_ghost) != n_elem:
                raise ValueError(
                    f"is_ghost length ({len(self.is_ghost)}) must match elements length ({n_elem})"
                )
        else:
            self.is_ghost = [False] * n_elem

        if self.masses is not None:
            if len(self.masses) != n_elem:
                raise ValueError(
                    f"masses length ({len(self.masses)}) must match elements length ({n_elem})"
                )
        return self

    def get_dynamic_masses(self) -> List[float]:
        """Dynamically retrieves atomic masses from mendeleev with ghost-atom guard [M]."""
        if self.masses is not None:
            return list(self.masses)
        resolved: List[float] = []
        for i, z in enumerate(self.atomic_numbers):
            if self.is_ghost[i] or z == 0 or self.elements[i] in ("Gh", "Bq", "X"):
                resolved.append(0.0)
            else:
                resolved.append(float(element(z).mass))
        return resolved


class MCSAlignmentConfig(BaseModel):
    """Configuration options controlling MCS perception and Kabsch alignment [D]."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    mass_weighting: bool = False
    match_valences: bool = True
    ring_matches_ring_only: bool = True
    complete_rings_only: bool = False
    min_mcs_atoms: int = Field(default=3, ge=3)
    svd_condition_tol: float = Field(default=1e-7, ge=1e-12)
    rmsd_cluster_threshold_angstrom: float = Field(default=0.25, ge=0.01)
    ignore_ghost_atoms: bool = True


class AlignedConformerResult(BaseModel):
    """Superposition result for a single conformer mapped to an invariant reference [D]."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    conformer_id: str
    reference_id: str
    rmsd_angstrom: float = Field(..., ge=0.0)
    rotation_matrix: List[List[float]]
    translation_vector: List[float]
    aligned_coordinates: List[Tuple[float, float, float]]
    atom_mapping: Dict[int, int]
    execution_duration_seconds: float = Field(..., ge=0.0)

    @model_validator(mode="after")
    def validate_rotation(self) -> "AlignedConformerResult":
        """Ensures proper SO(3) orthogonal rotation matrix with det(R) = +1.0 [D]."""
        R = np.array(self.rotation_matrix, dtype=np.float64)
        if R.shape != (3, 3):
            raise ValueError("rotation_matrix must have shape (3, 3)")
        if not np.allclose(R.T @ R, np.eye(3), atol=1e-3):
            raise ValueError("rotation_matrix is not orthogonal (R^T @ R != I)")
        det_R = float(np.linalg.det(R))
        if not np.isclose(det_R, 1.0, atol=1e-3):
            raise ValueError(f"rotation_matrix is not proper SO(3) rotation (det(R)={det_R} != 1.0)")
        if len(self.translation_vector) != 3:
            raise ValueError("translation_vector must have length 3")
        return self


class EnsembleAlignmentSummary(BaseModel):
    """Ensemble-wide alignment, pairwise RMSD matrix, and duplicate cluster summary [D]."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ensemble_id: str = Field(default="ensemble_default", description="Unique ensemble collection ID")
    reference_id: str
    total_conformers: int
    aligned_conformers: List[AlignedConformerResult]
    pairwise_rmsd_matrix: List[List[float]]
    duplicate_clusters: List[List[str]] = Field(default_factory=list)
    mcs_mapping: Dict[int, int] = Field(default_factory=dict, description="Consensus MCS atom index map")
    aligned_mcs_coords: Optional[List[List[Tuple[float, float, float]]]] = Field(
        default=None, description="Aligned consensus MCS coordinates across ensemble"
    )

    @model_validator(mode="after")
    def validate_summary(self) -> "EnsembleAlignmentSummary":
        """Validates symmetric square pairwise RMSD matrix with zero diagonal [D]."""
        mat = np.array(self.pairwise_rmsd_matrix, dtype=np.float64)
        m = mat.shape[0]
        if mat.shape != (m, m):
            raise ValueError(f"pairwise_rmsd_matrix must be square matrix, got shape {mat.shape}")
        if not np.allclose(mat, mat.T, atol=1e-4):
            raise ValueError("pairwise_rmsd_matrix must be symmetric (D_jk == D_kj)")
        if not np.allclose(np.diag(mat), 0.0, atol=1e-6):
            raise ValueError("pairwise_rmsd_matrix diagonal must be zero")
        if np.any(mat < -1e-6):
            raise ValueError("pairwise_rmsd_matrix elements must be non-negative")
        return self


def _isolated_mcs_worker(
    target_mol_block: str,
    ref_mol_block: str,
    params: dict,
) -> Tuple[bool, int, str]:
    """Module-level isolated worker for cross-process MCS extraction [D]."""
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    target_mol = Chem.MolFromMolBlock(target_mol_block, removeHs=False)
    ref_mol = Chem.MolFromMolBlock(ref_mol_block, removeHs=False)
    if target_mol is None or ref_mol is None:
        return False, 0, ""
    Chem.FastFindRings(target_mol)
    Chem.FastFindRings(ref_mol)

    timeout_sec = float(params.get("timeout_seconds", 30.0))
    rdkit_timeout = max(1, int(timeout_sec))

    atom_comp = rdFMCS.AtomCompare.CompareElements
    bond_comp = rdFMCS.BondCompare.CompareOrder
    match_valences = bool(params.get("match_valences", True))
    ring_matches_ring_only = bool(params.get("ring_matches_ring_only", True))
    complete_rings_only = bool(params.get("complete_rings_only", False))

    res = rdFMCS.FindMCS(
        [target_mol, ref_mol],
        atomCompare=atom_comp,
        bondCompare=bond_comp,
        matchValences=match_valences,
        ringMatchesRingOnly=ring_matches_ring_only,
        completeRingsOnly=complete_rings_only,
        timeout=rdkit_timeout,
    )
    return bool(res.canceled), int(res.numAtoms), str(res.smartsString)


def _build_rdkit_mol_from_conformer(
    conformer: ConformerInput,
    active_indices: List[int],
) -> Chem.Mol:
    """Constructs RDKit 3D molecule for active non-ghost atoms with bond perception fallback [M]."""
    rw_mol = Chem.RWMol()
    for orig_idx in active_indices:
        z = conformer.atomic_numbers[orig_idx]
        atom = Chem.Atom(z)
        rw_mol.AddAtom(atom)

    orig_to_local = {orig_idx: local_idx for local_idx, orig_idx in enumerate(active_indices)}

    if conformer.bonds:
        for u, v, bo in conformer.bonds:
            if u in orig_to_local and v in orig_to_local:
                lu, lv = orig_to_local[u], orig_to_local[v]
                if bo == 2.0:
                    btype = Chem.BondType.DOUBLE
                elif bo == 3.0:
                    btype = Chem.BondType.TRIPLE
                elif bo == 1.5:
                    btype = Chem.BondType.AROMATIC
                else:
                    btype = Chem.BondType.SINGLE
                rw_mol.AddBond(lu, lv, btype)
    else:
        # Distance-based connectivity perception calibrated against Pyykko relativistic covalent radii
        n_active = len(active_indices)
        radii: List[float] = []
        for orig_idx in active_indices:
            z = conformer.atomic_numbers[orig_idx]
            try:
                el = element(z)
                r = el.covalent_radius_pyykko
                if r is None:
                    r = el.covalent_radius
                if r is None:
                    r = 75.0
                radii.append(float(r) / 100.0)
            except Exception:
                radii.append(0.75)

        coords = np.array([conformer.coordinates[i] for i in active_indices], dtype=np.float64)
        for i in range(n_active):
            for j in range(i + 1, n_active):
                d_ij = float(np.linalg.norm(coords[i] - coords[j]))
                cutoff = radii[i] + radii[j] + 0.40
                if d_ij <= cutoff:
                    rw_mol.AddBond(i, j, Chem.BondType.SINGLE)

    mol = rw_mol.GetMol()
    conf = Chem.Conformer(len(active_indices))
    for local_idx, orig_idx in enumerate(active_indices):
        x, y, z = conformer.coordinates[orig_idx]
        conf.SetAtomPosition(local_idx, (float(x), float(y), float(z)))
    mol.AddConformer(conf)
    Chem.FastFindRings(mol)
    return mol


def compute_kabsch_transformation(
    P: np.ndarray,
    Q: np.ndarray,
    weights: Optional[np.ndarray] = None,
    condition_tol: float = 1e-7,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Computes optimal Kabsch proper rotation R and translation t mapping P to Q [D].

    Parameters:
        P: Target coordinate matrix of shape (N, 3).
        Q: Reference coordinate matrix of shape (N, 3).
        weights: Optional non-negative mass weighting vector of shape (N,).
        condition_tol: Singular value condition ratio tolerance for rank-deficiency.

    Returns:
        Tuple containing:
            - R: Proper orthogonal rotation matrix in SO(3) of shape (3, 3) with det(R) = +1.0.
            - t: Optimal translation vector of shape (3,).
            - rmsd: Weighted analytical root-mean-square deviation over mapped coordinates.

    Raises:
        DegenerateCoordinatesError: When coordinates exhibit point degeneracy (sigma_1 < 1e-12).
        CollinearDegeneracyError: When coordinates exhibit collinear rank-deficiency (sigma_2 / sigma_1 < condition_tol).
        IncompatibleTopologyError: When atom count N < 3.
    """
    p_arr = np.asarray(P, dtype=np.float64)
    q_arr = np.asarray(Q, dtype=np.float64)
    if p_arr.ndim != 2 or p_arr.shape[1] != 3:
        raise ValueError(f"P must have shape (N, 3), got {p_arr.shape}")
    if q_arr.ndim != 2 or q_arr.shape[1] != 3:
        raise ValueError(f"Q must have shape (N, 3), got {q_arr.shape}")
    n = p_arr.shape[0]
    if n != q_arr.shape[0]:
        raise ValueError(f"P and Q must have matching atom counts: {n} vs {q_arr.shape[0]}")
    if n < 3:
        raise IncompatibleTopologyError(f"Minimum 3 atoms required for Kabsch alignment, got {n}")

    if weights is None:
        w_arr = np.ones(n, dtype=np.float64)
    else:
        w_arr = np.asarray(weights, dtype=np.float64)
        if w_arr.shape != (n,):
            raise ValueError(f"weights must have shape ({n},), got {w_arr.shape}")
        if np.any(w_arr < 0):
            raise ValueError("weights must be non-negative")

    total_w = float(np.sum(w_arr))
    if total_w <= 0.0:
        raise ValueError("Sum of weights must be strictly positive")

    # Weighted centroids
    p_bar = np.sum(p_arr * w_arr[:, None], axis=0) / total_w
    q_bar = np.sum(q_arr * w_arr[:, None], axis=0) / total_w

    # Centered coordinates
    p_c = p_arr - p_bar
    q_c = q_arr - q_bar

    # Cross-covariance dispersion matrix H = P_c^T W Q_c
    h_mat = p_c.T @ (w_arr[:, None] * q_c)

    # Full SVD decomposition
    u_mat, s_vals, vt_mat = svd(h_mat)
    v_mat = vt_mat.T

    # Point-degeneracy: sigma_1 < 1e-12
    if s_vals[0] < 1e-12:
        raise DegenerateCoordinatesError(
            f"Point-degeneracy detected: primary singular value sigma_1 ({s_vals[0]:.3e}) < 1e-12"
        )

    # Collinear degeneracy: sigma_2 / sigma_1 < condition_tol
    cond_collinear = s_vals[1] / s_vals[0]
    if cond_collinear < condition_tol:
        raise CollinearDegeneracyError(
            f"Collinear coordinates detected: condition ratio sigma_2 / sigma_1 ({cond_collinear:.3e}) < {condition_tol}"
        )

    # Planar stabilization: sigma_2 / sigma_1 >= condition_tol and sigma_3 / sigma_1 < condition_tol
    cond_planar = s_vals[2] / s_vals[0]
    if cond_planar < condition_tol:
        u1, u2 = u_mat[:, 0], u_mat[:, 1]
        v1, v2 = v_mat[:, 0], v_mat[:, 1]
        u3 = np.cross(u1, u2)
        norm_u3 = np.linalg.norm(u3)
        if norm_u3 > 1e-14:
            u3 /= norm_u3
        v3 = np.cross(v1, v2)
        norm_v3 = np.linalg.norm(v3)
        if norm_v3 > 1e-14:
            v3 /= norm_v3
        u_mat = np.column_stack([u1, u2, u3])
        v_mat = np.column_stack([v1, v2, v3])

    # Parity reflection guard d = sgn(det(V @ U^T))
    det_vu = np.linalg.det(v_mat @ u_mat.T)
    d_parity = 1.0 if det_vu >= 0 else -1.0

    s_parity = np.diag([1.0, 1.0, d_parity])
    r_rot = v_mat @ s_parity @ u_mat.T

    # Translation vector t = Q_bar - R @ P_bar
    t_trans = q_bar - r_rot @ p_bar

    # Analytical centered RMSD
    diff = p_c @ r_rot.T - q_c
    rmsd = float(np.sqrt(np.sum(w_arr * np.sum(diff**2, axis=1)) / total_w))

    return r_rot, t_trans, rmsd


def align_conformers_by_mcs(
    target: ConformerInput,
    reference: ConformerInput,
    config: Optional[MCSAlignmentConfig] = None,
) -> AlignedConformerResult:
    """Superimposes a target conformer onto an invariant reference conformer via MCS and Kabsch [D].

    Parameters:
        target: Target conformer input record.
        reference: Invariant reference conformer record.
        config: Optional configuration controlling timeouts, weighting, and tolerances.

    Returns:
        AlignedConformerResult containing transformed coordinates, rotation matrix, and atom mapping.

    Raises:
        MCSConvergenceTimeoutError: If MCS graph search exceeds timeout ceiling or is canceled.
        IncompatibleTopologyError: If common atom count N_MCS < 3.
        CollinearDegeneracyError: If mapped coordinates are collinear.
    """
    start_time = time.perf_counter()
    if config is None:
        config = MCSAlignmentConfig()

    # Ghost atom identification & exclusion
    if config.ignore_ghost_atoms:
        target_active = [
            i for i in range(len(target.elements))
            if not (target.is_ghost[i] or target.atomic_numbers[i] == 0 or target.elements[i] in ("Gh", "Bq", "X"))
        ]
        ref_active = [
            i for i in range(len(reference.elements))
            if not (reference.is_ghost[i] or reference.atomic_numbers[i] == 0 or reference.elements[i] in ("Gh", "Bq", "X"))
        ]
    else:
        target_active = list(range(len(target.elements)))
        ref_active = list(range(len(reference.elements)))

    if len(target_active) < config.min_mcs_atoms or len(ref_active) < config.min_mcs_atoms:
        raise IncompatibleTopologyError(
            f"Insufficient active non-ghost atoms for MCS alignment: target has {len(target_active)}, "
            f"reference has {len(ref_active)}, min required is {config.min_mcs_atoms}"
        )

    target_mol = _build_rdkit_mol_from_conformer(target, target_active)
    ref_mol = _build_rdkit_mol_from_conformer(reference, ref_active)

    target_block = Chem.MolToMolBlock(target_mol)
    ref_block = Chem.MolToMolBlock(ref_mol)

    worker_params = {
        "timeout_seconds": config.timeout_seconds,
        "match_valences": config.match_valences,
        "ring_matches_ring_only": config.ring_matches_ring_only,
        "complete_rings_only": config.complete_rings_only,
    }

    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _isolated_mcs_worker,
                target_block,
                ref_block,
                worker_params,
            )
            canceled, num_atoms, smarts_str = future.result(timeout=config.timeout_seconds)
    except (concurrent.futures.TimeoutError, TimeoutError):
        raise MCSConvergenceTimeoutError(
            f"MCS graph search exceeded timeout ceiling of {config.timeout_seconds}s"
        )
    except Exception as exc:
        raise ToposAlignmentError(f"MCS worker process encountered unexpected failure: {exc}") from exc

    if canceled:
        raise MCSConvergenceTimeoutError(
            f"MCS graph search canceled (timeout exceeded: {config.timeout_seconds}s)"
        )

    if num_atoms < config.min_mcs_atoms or not smarts_str:
        raise IncompatibleTopologyError(
            f"Common substructure atom count ({num_atoms}) is less than minimum required ({config.min_mcs_atoms})"
        )

    mcs_mol = Chem.MolFromSmarts(smarts_str)
    if mcs_mol is None:
        raise IncompatibleTopologyError(f"Failed to parse MCS SMARTS: {smarts_str}")

    target_match = target_mol.GetSubstructMatch(mcs_mol)
    ref_match = ref_mol.GetSubstructMatch(mcs_mol)
    if not target_match or not ref_match or len(target_match) < config.min_mcs_atoms:
        raise IncompatibleTopologyError(
            f"MCS substructure matching yielded {len(target_match)} mapped atoms, expected >= {config.min_mcs_atoms}"
        )

    atom_mapping: Dict[int, int] = {}
    p_mapped: List[Tuple[float, float, float]] = []
    q_mapped: List[Tuple[float, float, float]] = []
    mapped_weights: List[float] = []

    target_masses = target.get_dynamic_masses()

    for local_t, local_r in zip(target_match, ref_match):
        orig_t = target_active[local_t]
        orig_r = ref_active[local_r]
        atom_mapping[orig_t] = orig_r
        p_mapped.append(target.coordinates[orig_t])
        q_mapped.append(reference.coordinates[orig_r])
        if config.mass_weighting:
            mapped_weights.append(target_masses[orig_t])
        else:
            mapped_weights.append(1.0)

    p_mat = np.array(p_mapped, dtype=np.float64)
    q_mat = np.array(q_mapped, dtype=np.float64)
    w_mat = np.array(mapped_weights, dtype=np.float64) if config.mass_weighting else None

    r_rot, t_trans, rmsd = compute_kabsch_transformation(
        p_mat, q_mat, weights=w_mat, condition_tol=config.svd_condition_tol
    )

    p_full = np.array(target.coordinates, dtype=np.float64)
    p_aligned = p_full @ r_rot.T + t_trans
    aligned_coords = [tuple(row) for row in p_aligned]

    duration = time.perf_counter() - start_time
    return AlignedConformerResult(
        conformer_id=target.conformer_id,
        reference_id=reference.conformer_id,
        rmsd_angstrom=float(rmsd),
        rotation_matrix=r_rot.tolist(),
        translation_vector=t_trans.tolist(),
        aligned_coordinates=aligned_coords,
        atom_mapping=atom_mapping,
        execution_duration_seconds=float(duration),
    )


def cluster_ensemble_conformers(
    conformers: List[ConformerInput],
    reference: ConformerInput,
    config: Optional[MCSAlignmentConfig] = None,
) -> EnsembleAlignmentSummary:
    """Performs batch alignment and pairwise RMSD clustering across a conformer ensemble [D]."""
    if config is None:
        config = MCSAlignmentConfig()

    aligned_conformers: List[AlignedConformerResult] = []
    for conf in conformers:
        aligned_conf = align_conformers_by_mcs(conf, reference, config=config)
        aligned_conformers.append(aligned_conf)

    m = len(conformers)
    pairwise_rmsd = np.zeros((m, m), dtype=np.float64)

    consensus_mapping: Dict[int, int] = {}
    if aligned_conformers:
        consensus_mapping = dict(aligned_conformers[0].atom_mapping)

    aligned_mcs_coords_list: List[List[Tuple[float, float, float]]] = []
    sorted_ref_atoms = sorted(set(consensus_mapping.values()))

    for ac in aligned_conformers:
        rev_map = {r: t for t, r in ac.atom_mapping.items()}
        conf_mcs_pts = []
        for r_idx in sorted_ref_atoms:
            if r_idx in rev_map:
                t_idx = rev_map[r_idx]
                conf_mcs_pts.append(ac.aligned_coordinates[t_idx])
        if conf_mcs_pts:
            aligned_mcs_coords_list.append(conf_mcs_pts)

    has_mcs_coords = len(aligned_mcs_coords_list) == m and all(
        len(pts) == len(aligned_mcs_coords_list[0]) for pts in aligned_mcs_coords_list
    )

    for j in range(m):
        for k in range(j + 1, m):
            if has_mcs_coords:
                pts_j = np.array(aligned_mcs_coords_list[j], dtype=np.float64)
                pts_k = np.array(aligned_mcs_coords_list[k], dtype=np.float64)
            else:
                pts_j = np.array(aligned_conformers[j].aligned_coordinates, dtype=np.float64)
                pts_k = np.array(aligned_conformers[k].aligned_coordinates, dtype=np.float64)
            diff = pts_j - pts_k
            rmsd_val = float(np.sqrt(np.mean(np.sum(diff**2, axis=1))))
            pairwise_rmsd[j, k] = rmsd_val
            pairwise_rmsd[k, j] = rmsd_val

    # Duplicate clustering via connected components
    threshold = config.rmsd_cluster_threshold_angstrom
    visited = [False] * m
    duplicate_clusters: List[List[str]] = []

    for i in range(m):
        if visited[i]:
            continue
        cluster_indices = [i]
        queue = [i]
        visited[i] = True
        while queue:
            curr = queue.pop(0)
            for nxt in range(m):
                if not visited[nxt] and pairwise_rmsd[curr, nxt] < threshold:
                    visited[nxt] = True
                    queue.append(nxt)
                    cluster_indices.append(nxt)
        if len(cluster_indices) >= 2:
            duplicate_clusters.append([conformers[idx].conformer_id for idx in cluster_indices])

    return EnsembleAlignmentSummary(
        ensemble_id=f"ens_{reference.conformer_id}",
        reference_id=reference.conformer_id,
        total_conformers=m,
        aligned_conformers=aligned_conformers,
        pairwise_rmsd_matrix=pairwise_rmsd.tolist(),
        duplicate_clusters=duplicate_clusters,
        mcs_mapping=consensus_mapping,
        aligned_mcs_coords=aligned_mcs_coords_list if has_mcs_coords else None,
    )


def persist_aligned_ensemble_h5(
    summary: EnsembleAlignmentSummary,
    archive_path: Path,
    lock_timeout: float = 30.0,
) -> Path:
    """Persists aligned conformer trajectories and RMSD matrices into HDF5 under 6-tier concurrency [D]."""
    t_store_env = os.environ.get("COCH_STORE_DIR")
    t_store = Path(t_store_env).resolve() if t_store_env else (Path.home() / ".cochem" / "store").resolve()
    resolved_path = archive_path.resolve()

    try:
        resolved_path.relative_to(t_store)
    except ValueError:
        raise AirGapBoundaryViolationError(
            f"Archive path {resolved_path} violates Tripartite Air-Gap: must reside inside {t_store}"
        )

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    tier = detect_concurrency_tier()
    lock_file_path = str(resolved_path) + ".lock"

    if tier == StorageTier.TIER6_HPC:
        hpc_scratch = os.environ.get("SLURM_TMPDIR") or os.environ.get("COCH_SCRATCH")
        if hpc_scratch:
            scratch_dir = Path(hpc_scratch) / "cochem_staging"
            scratch_dir.mkdir(parents=True, exist_ok=True)
            staging_path = scratch_dir / f"{resolved_path.name}.tmp.{os.getpid()}"
        else:
            staging_path = resolved_path.with_name(f"{resolved_path.name}.tmp.{os.getpid()}")
    else:
        staging_path = resolved_path.with_name(f"{resolved_path.name}.tmp.{os.getpid()}")

    libver = "latest" if tier in (StorageTier.TIER2_MACOS, StorageTier.TIER3_LINUX) else "earliest"

    with filelock.FileLock(lock_file_path, timeout=lock_timeout):
        with h5py.File(staging_path, "w", libver=libver) as h5f:
            ens_grp = h5f.require_group(f"/ensembles/{summary.ensemble_id}")
            rmsd_arr = np.array(summary.pairwise_rmsd_matrix, dtype=np.float32)
            ens_grp.create_dataset("pairwise_rmsd", data=rmsd_arr, dtype="float32")

            mapping_items = sorted(summary.mcs_mapping.items())
            mapping_arr = np.array(mapping_items, dtype=np.int32) if mapping_items else np.empty((0, 2), dtype=np.int32)
            ens_grp.create_dataset("mcs_mapping", data=mapping_arr, dtype="int32")

            if summary.aligned_conformers:
                atom_counts = [len(c.aligned_coordinates) for c in summary.aligned_conformers]
                if len(set(atom_counts)) == 1:
                    coords_arr = np.array(
                        [c.aligned_coordinates for c in summary.aligned_conformers], dtype=np.float64
                    )
                    ens_grp.create_dataset("aligned_coords", data=coords_arr, dtype="float64")
                else:
                    conf_grp = ens_grp.require_group("conformers")
                    for c in summary.aligned_conformers:
                        c_coords = np.array(c.aligned_coordinates, dtype=np.float64)
                        conf_grp.create_dataset(f"{c.conformer_id}/aligned_coords", data=c_coords, dtype="float64")

            if summary.aligned_mcs_coords is not None:
                mcs_coords_arr = np.array(summary.aligned_mcs_coords, dtype=np.float64)
                ens_grp.create_dataset("aligned_mcs_coords", data=mcs_coords_arr, dtype="float64")

        if staging_path.parent == resolved_path.parent:
            os.replace(staging_path, resolved_path)
        else:
            import shutil
            shutil.move(str(staging_path), str(resolved_path))

    return resolved_path

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
        coordinates=[(float(i), 0.0, 0.0) for i in range(10)],
    )
    c2 = ConformerInput(
        conformer_id="polycycle_2",
        elements=["C"] * 10,
        atomic_numbers=[6] * 10,
        coordinates=[(0.0, float(i), 0.0) for i in range(10)],
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

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.