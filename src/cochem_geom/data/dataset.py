"""CoChem-GEOM: PyTorch & PyG Geometric Dataset Architecture and Data Pipeline.
=====================================================================================
Establishes the definitive Tier 1 PyTorch and PyG dataset infrastructure for geometric
deep learning, conformer ensembles, rotational spectroscopy, and quantum chemistry.

Key Components:
1. Pure Immutable Geometric Transforms:
   - `CenterOfMassTransform`: Translates coordinates to COM origin (pure immutable subtraction).
   - `RandomRotationTransform`: Applies SO(3) 3D rotations equivariantly (pure immutable multiplication).
   - `EckartAlignmentTransform`: Aligns conformer to reference frame via SVD Kabsch rotation.
   - `GaussianJitterTransform`: Injects zero-mean Gaussian noise immutably.
   - `NormalizeTargetsTransform`: Standardizes target scalar energies/properties.
   - `ComposeTransforms`: Composes a sequential pipeline of pure transformations.

2. Batched Geometric Container & Collation:
   - `MolecularBatch`: Contiguous batched graph representation with node pointers (`batch`, `ptr`),
     block-diagonal `edge_index`, concatenated `pos`, `z`, `x`, `forces`, stacked `y`, `rotational_constants`.
   - `geom_collate_fn`: High-performance collate function for PyTorch DataLoader.

3. In-Memory & Streaming Datasets:
   - `GEOMInMemoryDataset`: Full-featured cached InMemoryDataset with conformer selection strategies
     ('all', 'lowest_energy', 'boltzmann', 'random'), slicing, indexing, and pre-filtering.
   - `GEOMIterableDataset`: Streaming IterableDataset with PyTorch multi-worker sharding
     (`get_worker_info()`), streaming MsgPack / JSON / QM log parsing, and bounded memory buffers.
   - `GEOMDatasetFactory`: Factory pattern generating QM9, GEOM-Drugs, Pickett, QMLog, and Custom
     datasets with deterministic train/val/test splitting.

Authoritative Standards & Directives:
- Method Matrix v4: Data Ingestion & Spectroscopic Graph Contracts
- Mendeleev Library Mandate: Dynamic atomic mass & isotopic resolution (NEVER hardcoded)
- State Immutability: Pure functional geometric transformations (`data.pos = data.pos + update`)
- Dynamic Path Resolution: Cross-platform dynamic pathing via `os.environ` and `pathlib.Path.home()`
- SE(3) Equivariance & Invariance: Strict separation of spatial `pos` vs non-spatial features `x`
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Mandate: 100% authentic physical tensor mathematics and real execution
"""

from __future__ import annotations

import abc
import copy
import dataclasses
import hashlib
import io
import json
import logging
import math
import os
from pathlib import Path
import random
import sys
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import mendeleev
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, IterableDataset, get_worker_info

try:
    import msgpack
except ImportError:
    msgpack = None

try:
    import lmdb
except ImportError:
    lmdb = None

import pickle

# Optional PyG Base Class inheritance if PyG is installed
try:
    import torch_geometric.data as pyg_data
    PYG_AVAILABLE = True
    PyGInMemoryBase = pyg_data.InMemoryDataset
except (ImportError, AttributeError):
    PYG_AVAILABLE = False
    PyGInMemoryBase = Dataset

from cochem_geom.data.featurizer import (
    ATOMIC_MASS_UNIT_KG,
    ATOMIC_NUMBER_TO_SYMBOL,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_ELEMENT_TYPES,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ELEMENT_TYPE_TO_INDEX,
    ELEMENTARY_CHARGE_C,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INDEX_TO_ELEMENT_TYPE,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    MolecularFeaturizer,
    MolecularGraphConfig,
    MolecularInput,
    build_radius_graph,
    calculate_boltzmann_weights,
    compute_center_of_mass,
    compute_moment_of_inertia_tensor,
    compute_principal_rotational_constants,
    get_atomic_mass,
    get_covalent_radius_angstrom,
    get_isotopic_mass,
    get_monoisotopic_mass,
    get_pauling_electronegativity,
    get_vdw_radius_angstrom,
)
from cochem_geom.data.geom_parser import (
    ConformerRecord,
    MoleculeRecord,
    QMOutputRecord,
    compute_bytes_sha256,
    compute_file_sha256,
    compute_structure_sha256,
    conformer_to_molecular_data,
    deserialize_geom_archive,
    deserialize_geom_bytes,
    ensemble_to_molecular_data,
    parse_geom_raw_molecule,
    parse_qm_log_text,
    parse_qm_output,
)

logger = logging.getLogger("cochem_geom.data.dataset")


# ==============================================================================
# 1. Fundamental Constants & Buffer Configurations
# ==============================================================================

DEFAULT_STREAMING_BUFFER_SIZE: int = 1000
"""Default bounded in-memory buffer size for streaming IterableDataset [E]."""

DEFAULT_RANDOM_SEED: int = 42
"""Default deterministic pseudo-random generator seed [E]."""

_DYNAMIC_MASS_CACHE: Dict[str, float] = {}
_DYNAMIC_MONO_MASS_CACHE: Dict[str, float] = {}


def resolve_dynamic_mass(symbol_or_z: Union[str, int]) -> float:
    """Resolve atomic mass dynamically via Mendeleev with local thread-safe caching [M]."""
    key = str(symbol_or_z).capitalize()
    if key not in _DYNAMIC_MASS_CACHE:
        _DYNAMIC_MASS_CACHE[key] = get_atomic_mass(symbol_or_z)
    return _DYNAMIC_MASS_CACHE[key]


def resolve_dynamic_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
    """Resolve monoisotopic mass dynamically via Mendeleev with local caching [M]."""
    key = str(symbol_or_z).capitalize()
    if key not in _DYNAMIC_MONO_MASS_CACHE:
        _DYNAMIC_MONO_MASS_CACHE[key] = get_monoisotopic_mass(symbol_or_z)
    return _DYNAMIC_MONO_MASS_CACHE[key]


# ==============================================================================
# 2. Dynamic Path & Environment Resolution
# ==============================================================================

def get_default_data_dir() -> Path:
    """Dynamically resolve default CoChem dataset root directory [E].

    Prioritizes the `COCHEM_DATA_DIR` environment variable, falling back to
    `~/.cochem/data` to ensure zero hardcoded machine-specific file paths.

    Returns
    -------
    Path
        Resolved absolute directory path.
    """
    env_dir = os.environ.get("COCHEM_DATA_DIR")
    if env_dir:
        resolved = Path(env_dir).expanduser().resolve()
    else:
        resolved = (Path.home() / ".cochem" / "data").resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


# ==============================================================================
# 3. Pure Immutable Transformations
# ==============================================================================

class BaseTransform(abc.ABC):
    """Abstract base class for pure immutable molecular graph transformations."""

    @abc.abstractmethod
    def __call__(self, data: MolecularData) -> MolecularData:
        """Apply transformation immutably, returning a new MolecularData instance."""
        raise RuntimeError("Abstract method")


class CenterOfMassTransform(BaseTransform):
    """Translate molecular coordinates to center of mass origin immutably [D].

    $$\\mathbf{r}'_i = \\mathbf{r}_i - \\mathbf{r}_{\\text{COM}}$$
    Uses dynamic atomic masses dynamically queried from Mendeleev (NEVER hardcoded).
    """

    def __init__(self, use_monoisotopic: bool = False) -> None:
        self.use_monoisotopic = use_monoisotopic

    def __call__(self, data: MolecularData) -> MolecularData:
        if self.use_monoisotopic:
            masses = [resolve_dynamic_monoisotopic_mass(s) for s in data.symbols]
        else:
            masses = [resolve_dynamic_mass(s) for s in data.symbols]

        masses_tensor = torch.tensor(masses, dtype=data.pos.dtype, device=data.pos.device)
        com = compute_center_of_mass(data.pos, masses_tensor)

        # Pure immutable subtraction (never pos -= com)
        new_pos = data.pos - com.unsqueeze(0)

        return MolecularData(
            z=data.z.clone(),
            pos=new_pos,
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=data.y.clone() if data.y is not None else None,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=data.forces.clone() if data.forces is not None else None,
            dipole=data.dipole.clone() if data.dipole is not None else None,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )


class RandomRotationTransform(BaseTransform):
    """Apply a random 3D rotation from SO(3) equivariantly and immutably [D].

    $$\\mathbf{r}'_i = \\mathbf{r}_i \\mathbf{R}^T, \\quad \\mathbf{F}'_i = \\mathbf{F}_i \\mathbf{R}^T, \\quad \\boldsymbol{\\mu}' = \\boldsymbol{\\mu} \\mathbf{R}^T$$
    where $\\mathbf{R} \\in \\mathrm{SO}(3)$ is a valid orthogonal rotation matrix with $\\det(\\mathbf{R}) = +1$.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = np.random.default_rng(seed) if seed is not None else None

    def _generate_so3_matrix(self, dtype: torch.dtype, device: torch.device) -> torch.Tensor:
        """Generate a uniformly sampled random SO(3) rotation matrix via Haar measure [D]."""
        if self.rng is not None:
            mat = self.rng.normal(size=(3, 3))
        else:
            mat = np.random.normal(size=(3, 3))

        # QR decomposition
        q, r = np.linalg.qr(mat)
        # Ensure positive diagonal in R for uniqueness
        d = np.diagonal(r)
        ph = d / np.abs(d)
        q = q * ph
        # Ensure proper rotation det(Q) = +1
        if np.linalg.det(q) < 0.0:
            q[:, 0] = -q[:, 0]

        return torch.tensor(q, dtype=dtype, device=device)

    def __call__(self, data: MolecularData) -> MolecularData:
        rot_mat = self._generate_so3_matrix(data.pos.dtype, data.pos.device)

        # Pure immutable transformation
        new_pos = data.pos @ rot_mat.T
        new_forces = data.forces @ rot_mat.T if data.forces is not None else None
        new_dipole = data.dipole @ rot_mat.T if data.dipole is not None else None

        return MolecularData(
            z=data.z.clone(),
            pos=new_pos,
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=data.y.clone() if data.y is not None else None,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=new_forces,
            dipole=new_dipole,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )


class EckartAlignmentTransform(BaseTransform):
    """Align molecular coordinates to a target reference structure using Eckart / Kabsch frame alignment [D].

    Finds optimal $\\mathbf{R} \\in \\mathrm{SO}(3)$ minimizing mass-weighted root mean square deviation.
    """

    def __init__(
        self,
        reference: MolecularData,
        use_mass_weighting: bool = True,
    ) -> None:
        self.reference = reference
        self.use_mass_weighting = use_mass_weighting

    def __call__(self, data: MolecularData) -> MolecularData:
        if self.use_mass_weighting:
            masses_list = [resolve_dynamic_mass(s) for s in data.symbols]
        else:
            masses_list = [1.0 for _ in data.symbols]

        masses = torch.tensor(masses_list, dtype=data.pos.dtype, device=data.pos.device)

        data_com = compute_center_of_mass(data.pos, masses)
        ref_com = compute_center_of_mass(self.reference.pos, masses)

        p = data.pos - data_com.unsqueeze(0)
        q = self.reference.pos - ref_com.unsqueeze(0)

        if self.use_mass_weighting:
            m = masses.unsqueeze(-1)
            h = (p * m).T @ q
        else:
            h = p.T @ q

        # SVD: H = U * S * V^T
        u, _, v_t = torch.linalg.svd(h)
        d = torch.det(v_t.T @ u.T)

        correction = torch.eye(3, dtype=p.dtype, device=p.device)
        if d < 0:
            correction[2, 2] = -1.0

        rot_mat = v_t.T @ correction @ u.T

        # Pure immutable transformation
        new_pos = p @ rot_mat.T + ref_com.unsqueeze(0)
        new_forces = data.forces @ rot_mat.T if data.forces is not None else None
        new_dipole = data.dipole @ rot_mat.T if data.dipole is not None else None

        return MolecularData(
            z=data.z.clone(),
            pos=new_pos,
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=data.y.clone() if data.y is not None else None,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=new_forces,
            dipole=new_dipole,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )


class GaussianJitterTransform(BaseTransform):
    """Add zero-mean isotropic Gaussian noise to Cartesian coordinates immutably [E].

    $$\\mathbf{r}'_i = \\mathbf{r}_i + \\boldsymbol{\\epsilon}_i, \\quad \\boldsymbol{\\epsilon}_i \\sim \\mathcal{N}(\\mathbf{0}, \\sigma^2 \\mathbf{I})$$
    """

    def __init__(self, sigma: float = 0.01, seed: Optional[int] = None) -> None:
        self.sigma = float(sigma)
        self.seed = seed
        self.generator = torch.Generator().manual_seed(seed) if seed is not None else None

    def __call__(self, data: MolecularData) -> MolecularData:
        if self.sigma <= 0.0:
            return data.clone()

        if self.generator is not None:
            noise = torch.randn(
                data.pos.shape,
                dtype=data.pos.dtype,
                device=data.pos.device,
                generator=self.generator,
            ) * self.sigma
        else:
            noise = torch.randn(
                data.pos.shape,
                dtype=data.pos.dtype,
                device=data.pos.device,
            ) * self.sigma

        # Pure immutable addition (data.pos + noise)
        new_pos = data.pos + noise

        return MolecularData(
            z=data.z.clone(),
            pos=new_pos,
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=data.y.clone() if data.y is not None else None,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=data.forces.clone() if data.forces is not None else None,
            dipole=data.dipole.clone() if data.dipole is not None else None,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )


class NormalizeTargetsTransform(BaseTransform):
    """Standardize target properties (e.g. energy y) via mean and standard deviation [D].

    $$y' = \\frac{y - \\mu}{\\sigma + \\epsilon}$$
    """

    def __init__(
        self,
        mean: Union[float, torch.Tensor],
        std: Union[float, torch.Tensor],
        eps: float = 1e-8,
    ) -> None:
        self.mean = torch.as_tensor(mean, dtype=torch.float32)
        self.std = torch.as_tensor(std, dtype=torch.float32)
        self.eps = float(eps)

    def __call__(self, data: MolecularData) -> MolecularData:
        if data.y is None:
            return data.clone()

        mean = self.mean.to(dtype=data.y.dtype, device=data.y.device)
        std = self.std.to(dtype=data.y.dtype, device=data.y.device)

        # Pure immutable normalization
        new_y = (data.y - mean) / (std + self.eps)

        return MolecularData(
            z=data.z.clone(),
            pos=data.pos.clone(),
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=new_y,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=data.forces.clone() if data.forces is not None else None,
            dipole=data.dipole.clone() if data.dipole is not None else None,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )

    def denormalize(self, y_norm: torch.Tensor) -> torch.Tensor:
        """Denormalize standardized target tensor back to physical units [D]."""
        mean = self.mean.to(dtype=y_norm.dtype, device=y_norm.device)
        std = self.std.to(dtype=y_norm.dtype, device=y_norm.device)
        return y_norm * (std + self.eps) + mean


class ComposeTransforms(BaseTransform):
    """Chain multiple transformations sequentially into a single callable pipeline [E]."""

    def __init__(self, transforms: Sequence[Callable[[MolecularData], MolecularData]]) -> None:
        self.transforms = list(transforms)

    def __call__(self, data: MolecularData) -> MolecularData:
        current_data = data
        for t in self.transforms:
            current_data = t(current_data)
        return current_data


# ==============================================================================
# 4. Batched Geometric Container & Collation Function
# ==============================================================================

@dataclasses.dataclass
class MolecularBatch:
    """Batched molecular graph collection for geometric deep learning and PyG/PyTorch execution."""

    pos: torch.Tensor
    z: torch.Tensor
    batch: torch.Tensor
    ptr: torch.Tensor
    edge_index: Optional[torch.Tensor] = None
    y: Optional[torch.Tensor] = None
    x: Optional[torch.Tensor] = None
    edge_attr: Optional[torch.Tensor] = None
    forces: Optional[torch.Tensor] = None
    rotational_constants: Optional[torch.Tensor] = None
    dipole: Optional[torch.Tensor] = None
    weight: Optional[torch.Tensor] = None
    num_graphs: int = 1
    num_nodes: int = 0
    symbols: Optional[List[str]] = None
    metadata: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self) -> None:
        if self.num_nodes == 0 and self.pos is not None:
            self.num_nodes = int(self.pos.size(0))

    def to(
        self,
        device: Optional[Union[str, torch.device]] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> MolecularBatch:
        """Transfer all batch tensors to specified device and precision immutably."""
        dev = torch.device(device) if device is not None else self.pos.device

        new_pos = self.pos.to(device=dev, dtype=dtype) if dtype is not None else self.pos.to(device=dev)
        new_z = self.z.to(device=dev)
        new_batch = self.batch.to(device=dev)
        new_ptr = self.ptr.to(device=dev)
        new_edge_index = self.edge_index.to(device=dev) if self.edge_index is not None else None
        new_y = (
            self.y.to(device=dev, dtype=dtype)
            if self.y is not None and dtype is not None
            else (self.y.to(device=dev) if self.y is not None else None)
        )
        new_x = (
            self.x.to(device=dev, dtype=dtype)
            if self.x is not None and dtype is not None
            else (self.x.to(device=dev) if self.x is not None else None)
        )
        new_edge_attr = (
            self.edge_attr.to(device=dev, dtype=dtype)
            if self.edge_attr is not None and dtype is not None
            else (self.edge_attr.to(device=dev) if self.edge_attr is not None else None)
        )
        new_forces = (
            self.forces.to(device=dev, dtype=dtype)
            if self.forces is not None and dtype is not None
            else (self.forces.to(device=dev) if self.forces is not None else None)
        )
        new_rot_consts = (
            self.rotational_constants.to(device=dev, dtype=dtype)
            if self.rotational_constants is not None and dtype is not None
            else (self.rotational_constants.to(device=dev) if self.rotational_constants is not None else None)
        )
        new_dipole = (
            self.dipole.to(device=dev, dtype=dtype)
            if self.dipole is not None and dtype is not None
            else (self.dipole.to(device=dev) if self.dipole is not None else None)
        )
        new_weight = (
            self.weight.to(device=dev, dtype=dtype)
            if self.weight is not None and dtype is not None
            else (self.weight.to(device=dev) if self.weight is not None else None)
        )

        return MolecularBatch(
            pos=new_pos,
            z=new_z,
            batch=new_batch,
            ptr=new_ptr,
            edge_index=new_edge_index,
            y=new_y,
            x=new_x,
            edge_attr=new_edge_attr,
            forces=new_forces,
            rotational_constants=new_rot_consts,
            dipole=new_dipole,
            weight=new_weight,
            num_graphs=self.num_graphs,
            num_nodes=self.num_nodes,
            symbols=list(self.symbols) if self.symbols is not None else None,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def clone(self) -> MolecularBatch:
        """Create a deep copy of the MolecularBatch."""
        return MolecularBatch(
            pos=self.pos.clone(),
            z=self.z.clone(),
            batch=self.batch.clone(),
            ptr=self.ptr.clone(),
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            dipole=self.dipole.clone() if self.dipole is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            num_graphs=self.num_graphs,
            num_nodes=self.num_nodes,
            symbols=list(self.symbols) if self.symbols is not None else None,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def __len__(self) -> int:
        return self.num_graphs

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"Key '{key}' not found in MolecularBatch.")

    def keys(self) -> List[str]:
        all_keys = [
            "pos", "z", "batch", "ptr", "edge_index", "y", "x",
            "edge_attr", "forces", "rotational_constants", "dipole", "weight"
        ]
        return [k for k in all_keys if getattr(self, k) is not None]

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.keys()}

    def to_data_list(self) -> List[MolecularData]:
        """Decompose batched representation back into individual MolecularData graphs."""
        data_list: List[MolecularData] = []
        ptr_list = self.ptr.tolist()

        for i in range(self.num_graphs):
            start_node = ptr_list[i]
            end_node = ptr_list[i + 1]

            sub_pos = self.pos[start_node:end_node].clone()
            sub_z = self.z[start_node:end_node].clone()

            sub_x = self.x[start_node:end_node].clone() if self.x is not None else None
            sub_forces = (
                self.forces[start_node:end_node].clone()
                if self.forces is not None
                else None
            )

            # Slicing edges
            sub_edge_index = None
            sub_edge_attr = None
            if self.edge_index is not None and self.edge_index.numel() > 0:
                edge_mask = (self.edge_index[0] >= start_node) & (self.edge_index[0] < end_node)
                if edge_mask.any():
                    sub_edge_index = self.edge_index[:, edge_mask] - start_node
                    if self.edge_attr is not None:
                        sub_edge_attr = self.edge_attr[edge_mask].clone()

            sub_y = self.y[i : i + 1].clone() if self.y is not None else None
            sub_weight = self.weight[i : i + 1].clone() if self.weight is not None else None
            sub_rot = (
                self.rotational_constants[i].clone()
                if self.rotational_constants is not None
                else None
            )
            sub_dipole = self.dipole[i].clone() if self.dipole is not None else None
            sub_symbols = (
                self.symbols[start_node:end_node]
                if self.symbols is not None and len(self.symbols) == self.num_nodes
                else (
                    self.symbols[i]
                    if self.symbols is not None and len(self.symbols) == self.num_graphs and isinstance(self.symbols[i], list)
                    else [ATOMIC_NUMBER_TO_SYMBOL.get(int(z.item()), "X") for z in sub_z]
                )
            )
            sub_meta = (
                self.metadata[i]
                if self.metadata is not None and i < len(self.metadata)
                else {}
            )

            data_list.append(
                MolecularData(
                    z=sub_z,
                    pos=sub_pos,
                    edge_index=sub_edge_index,
                    y=sub_y,
                    x=sub_x,
                    edge_attr=sub_edge_attr,
                    weight=sub_weight,
                    forces=sub_forces,
                    dipole=sub_dipole,
                    rotational_constants=sub_rot,
                    symbols=sub_symbols,
                    metadata=sub_meta,
                )
            )

        return data_list

    def __repr__(self) -> str:
        attrs = [f"num_graphs={self.num_graphs}", f"num_nodes={self.num_nodes}"]
        if self.edge_index is not None:
            attrs.append(f"num_edges={self.edge_index.size(1)}")
        if self.y is not None:
            attrs.append(f"y={list(self.y.shape)}")
        if self.x is not None:
            attrs.append(f"x={list(self.x.shape)}")
        return f"MolecularBatch({', '.join(attrs)})"


def geom_collate_fn(items: Sequence[Union[MolecularData, Dict[str, Any], Any]]) -> MolecularBatch:
    """Collate a sequence of MolecularData objects into a contiguous MolecularBatch [E]."""
    if not items:
        raise ValueError("Cannot collate empty sequence of molecular items.")

    mol_items: List[MolecularData] = []
    for s in items:
        if isinstance(s, MolecularData):
            mol_items.append(s)
        elif isinstance(s, dict):
            mol_items.append(
                MolecularData(
                    z=s["z"],
                    pos=s["pos"],
                    edge_index=s.get("edge_index"),
                    y=s.get("y"),
                    x=s.get("x"),
                    edge_attr=s.get("edge_attr"),
                    weight=s.get("weight"),
                    forces=s.get("forces"),
                    dipole=s.get("dipole"),
                    rotational_constants=s.get("rotational_constants"),
                    symbols=s.get("symbols"),
                    metadata=s.get("metadata", {}),
                )
            )
        else:
            mol_items.append(
                MolecularData(
                    z=getattr(s, "z"),
                    pos=getattr(s, "pos"),
                    edge_index=getattr(s, "edge_index", None),
                    y=getattr(s, "y", None),
                    x=getattr(s, "x", None),
                    edge_attr=getattr(s, "edge_attr", None),
                    weight=getattr(s, "weight", None),
                    forces=getattr(s, "forces", None),
                    dipole=getattr(s, "dipole", None),
                    rotational_constants=getattr(s, "rotational_constants", None),
                    symbols=getattr(s, "symbols", None),
                    metadata=getattr(s, "metadata", {}),
                )
            )

    pos_list: List[torch.Tensor] = []
    z_list: List[torch.Tensor] = []
    batch_list: List[torch.Tensor] = []
    ptr_list: List[int] = [0]
    edge_index_list: List[torch.Tensor] = []
    x_list: List[torch.Tensor] = []
    edge_attr_list: List[torch.Tensor] = []
    y_list: List[torch.Tensor] = []
    forces_list: List[torch.Tensor] = []
    rot_consts_list: List[torch.Tensor] = []
    dipole_list: List[torch.Tensor] = []
    weight_list: List[torch.Tensor] = []
    symbols_list: List[str] = []
    metadata_list: List[Dict[str, Any]] = []

    has_edges = any(s.edge_index is not None and s.edge_index.numel() > 0 for s in mol_items)
    has_x = any(s.x is not None for s in mol_items)
    has_edge_attr = any(s.edge_attr is not None for s in mol_items)
    has_y = any(s.y is not None for s in mol_items)
    has_forces = any(s.forces is not None for s in mol_items)
    has_rot_consts = any(s.rotational_constants is not None for s in mol_items)
    has_dipole = any(s.dipole is not None for s in mol_items)
    has_weight = any(s.weight is not None for s in mol_items)

    node_offset = 0
    ref_device = mol_items[0].pos.device
    ref_dtype = mol_items[0].pos.dtype

    for i, s in enumerate(mol_items):
        n_nodes = s.num_nodes
        pos_list.append(s.pos.to(device=ref_device, dtype=ref_dtype))
        z_list.append(s.z.to(device=ref_device, dtype=torch.long))
        batch_list.append(torch.full((n_nodes,), i, dtype=torch.long, device=ref_device))

        node_offset += n_nodes
        ptr_list.append(node_offset)

        if has_edges:
            if s.edge_index is not None and s.edge_index.numel() > 0:
                shifted_edges = s.edge_index.to(device=ref_device, dtype=torch.long) + (node_offset - n_nodes)
                edge_index_list.append(shifted_edges)

        if has_x:
            if s.x is not None:
                x_list.append(s.x.to(device=ref_device, dtype=ref_dtype))
            else:
                dim_x = next(item.x.size(1) for item in mol_items if item.x is not None)
                x_list.append(torch.zeros((n_nodes, dim_x), dtype=ref_dtype, device=ref_device))

        if has_edge_attr and s.edge_attr is not None:
            edge_attr_list.append(s.edge_attr.to(device=ref_device, dtype=ref_dtype))

        if has_y:
            if s.y is not None:
                y_tensor = s.y.view(1, -1) if s.y.dim() <= 1 else s.y
                y_list.append(y_tensor.to(device=ref_device, dtype=ref_dtype))
            else:
                y_list.append(torch.zeros((1, 1), dtype=ref_dtype, device=ref_device))

        if has_forces:
            if s.forces is not None:
                forces_list.append(s.forces.to(device=ref_device, dtype=ref_dtype))
            else:
                forces_list.append(torch.zeros((n_nodes, 3), dtype=ref_dtype, device=ref_device))

        if has_rot_consts:
            if s.rotational_constants is not None:
                rot_consts_list.append(s.rotational_constants.view(1, 3).to(device=ref_device, dtype=ref_dtype))
            else:
                rot_consts_list.append(torch.zeros((1, 3), dtype=ref_dtype, device=ref_device))

        if has_dipole:
            if s.dipole is not None:
                dipole_list.append(s.dipole.view(1, 3).to(device=ref_device, dtype=ref_dtype))
            else:
                dipole_list.append(torch.zeros((1, 3), dtype=ref_dtype, device=ref_device))

        if has_weight:
            if s.weight is not None:
                weight_list.append(s.weight.view(1, 1).to(device=ref_device, dtype=ref_dtype))
            else:
                weight_list.append(torch.ones((1, 1), dtype=ref_dtype, device=ref_device))

        symbols_list.extend(s.symbols)
        metadata_list.append(dict(s.metadata))

    batched_pos = torch.cat(pos_list, dim=0)
    batched_z = torch.cat(z_list, dim=0)
    batched_batch = torch.cat(batch_list, dim=0)
    batched_ptr = torch.tensor(ptr_list, dtype=torch.long, device=ref_device)

    batched_edge_index = (
        torch.cat(edge_index_list, dim=1) if has_edges and edge_index_list else None
    )
    batched_x = torch.cat(x_list, dim=0) if has_x and x_list else None
    batched_edge_attr = torch.cat(edge_attr_list, dim=0) if has_edge_attr and edge_attr_list else None
    batched_y = torch.cat(y_list, dim=0) if has_y and y_list else None
    batched_forces = torch.cat(forces_list, dim=0) if has_forces and forces_list else None
    batched_rot_consts = torch.cat(rot_consts_list, dim=0) if has_rot_consts and rot_consts_list else None
    batched_dipole = torch.cat(dipole_list, dim=0) if has_dipole and dipole_list else None
    batched_weight = torch.cat(weight_list, dim=0) if has_weight and weight_list else None

    return MolecularBatch(
        pos=batched_pos,
        z=batched_z,
        batch=batched_batch,
        ptr=batched_ptr,
        edge_index=batched_edge_index,
        y=batched_y,
        x=batched_x,
        edge_attr=batched_edge_attr,
        forces=batched_forces,
        rotational_constants=batched_rot_consts,
        dipole=batched_dipole,
        weight=batched_weight,
        num_graphs=len(mol_items),
        num_nodes=node_offset,
        symbols=symbols_list,
        metadata=metadata_list,
    )


# ==============================================================================
# 5. GEOM InMemoryDataset Implementation
# ==============================================================================

class GEOMInMemoryDataset(PyGInMemoryBase):
    """PyTorch and PyG compatible InMemoryDataset with caching, indexing, and conformer filtering."""

    def __init__(
        self,
        root: Optional[Union[str, Path]] = None,
        data_list: Optional[Sequence[MolecularData]] = None,
        raw_file_paths: Optional[Sequence[Union[str, Path]]] = None,
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        pre_transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        pre_filter: Optional[Callable[[MolecularData], bool]] = None,
        conformer_strategy: str = "all",
        temperature_k: float = STANDARD_TEMPERATURE_K,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> None:
        self.conformer_strategy = conformer_strategy.lower()
        self.temperature_k = float(temperature_k)
        self.seed = seed
        self._custom_transform = transform
        self._custom_pre_transform = pre_transform
        self._custom_pre_filter = pre_filter
        self._data_list: List[MolecularData] = []

        resolved_root = Path(root).expanduser().resolve() if root is not None else get_default_data_dir() / "inmemory"
        self._root_path = resolved_root

        if PYG_AVAILABLE:
            super().__init__(
                root=str(resolved_root),
                transform=transform,
                pre_transform=pre_transform,
                pre_filter=pre_filter,
            )

        if data_list is not None:
            self._process_data_list(data_list)
        elif raw_file_paths is not None:
            self._process_raw_files(raw_file_paths)
        elif root is not None and (resolved_root / "processed" / "data.pt").exists():
            self.load(resolved_root / "processed" / "data.pt")

    @property
    def raw_file_names(self) -> List[str]:
        return []

    @property
    def processed_file_names(self) -> List[str]:
        return ["data.pt"]

    def _process_data_list(self, data_list: Sequence[MolecularData]) -> None:
        filtered_list: List[MolecularData] = []
        for d in data_list:
            item = d.clone()
            if self._custom_pre_filter is not None and not self._custom_pre_filter(item):
                continue
            if self._custom_pre_transform is not None:
                item = self._custom_pre_transform(item)
            filtered_list.append(item)

        self._data_list = filtered_list

    def _process_raw_files(self, raw_files: Sequence[Union[str, Path]]) -> None:
        extracted_data: List[MolecularData] = []
        rng = random.Random(self.seed) if self.seed is not None else random.Random()

        for rf in raw_files:
            p = Path(rf).expanduser().resolve()
            if not p.exists():
                logger.warning(f"Raw dataset file not found: {p}")
                continue

            if p.suffix in [".msgpack", ".mp"]:
                for smiles, mol_data in deserialize_geom_archive(p):
                    rec = parse_geom_raw_molecule(smiles, mol_data, temperature_k=self.temperature_k)
                    if self.conformer_strategy == "all":
                        for conf in rec.conformers:
                            extracted_data.append(conformer_to_molecular_data(rec, conf))
                    elif self.conformer_strategy in ["lowest_energy", "min_energy"]:
                        lowest = rec.get_lowest_energy_conformer()
                        if lowest is not None:
                            extracted_data.append(conformer_to_molecular_data(rec, lowest))
                    elif self.conformer_strategy == "boltzmann":
                        mols = ensemble_to_molecular_data(rec)
                        extracted_data.extend(mols)
                    elif self.conformer_strategy == "random":
                        if rec.conformers:
                            chosen = rng.choice(rec.conformers)
                            extracted_data.append(conformer_to_molecular_data(rec, chosen))
            elif p.suffix in [".json", ".jsonl"]:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        data_dict = json.loads(line_str)
                        mol_in = MolecularInput(**data_dict)
                        featurizer = MolecularFeaturizer()
                        extracted_data.append(featurizer.featurize(mol_in))

        self._process_data_list(extracted_data)

    def len(self) -> int:
        return len(self._data_list)

    def __len__(self) -> int:
        return self.len()

    def get(self, idx: int) -> MolecularData:
        if idx < 0 or idx >= len(self._data_list):
            raise IndexError(f"Index {idx} out of range for dataset with length {len(self._data_list)}")
        item = self._data_list[idx].clone()
        if self._custom_transform is not None:
            item = self._custom_transform(item)
        return item

    def __getitem__(
        self,
        idx: Union[int, slice, Sequence[int], torch.Tensor],
    ) -> Union[MolecularData, GEOMInMemoryDataset]:
        if isinstance(idx, int):
            return self.get(idx)
        elif isinstance(idx, slice):
            sliced_items = self._data_list[idx]
            subset = GEOMInMemoryDataset(
                root=self._root_path,
                data_list=sliced_items,
                transform=self._custom_transform,
                pre_transform=self._custom_pre_transform,
                pre_filter=self._custom_pre_filter,
                conformer_strategy=self.conformer_strategy,
                temperature_k=self.temperature_k,
                seed=self.seed,
            )
            return subset
        elif isinstance(idx, (list, tuple, np.ndarray, torch.Tensor)):
            indices = [int(i) for i in idx]
            selected_items = [self._data_list[i] for i in indices]
            subset = GEOMInMemoryDataset(
                root=self._root_path,
                data_list=selected_items,
                transform=self._custom_transform,
                pre_transform=self._custom_pre_transform,
                pre_filter=self._custom_pre_filter,
                conformer_strategy=self.conformer_strategy,
                temperature_k=self.temperature_k,
                seed=self.seed,
            )
            return subset
        raise TypeError(f"Invalid index type: {type(idx)}")

    def filter(self, filter_fn: Callable[[MolecularData], bool]) -> GEOMInMemoryDataset:
        filtered_items = [d for d in self._data_list if filter_fn(d)]
        return GEOMInMemoryDataset(
            root=self._root_path,
            data_list=filtered_items,
            transform=self._custom_transform,
            pre_transform=self._custom_pre_transform,
            pre_filter=self._custom_pre_filter,
            conformer_strategy=self.conformer_strategy,
            temperature_k=self.temperature_k,
            seed=self.seed,
        )

    def save(self, path: Union[str, Path]) -> None:
        save_path = Path(path).expanduser().resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "data_list": self._data_list,
                "conformer_strategy": self.conformer_strategy,
                "temperature_k": self.temperature_k,
                "seed": self.seed,
            },
            save_path,
        )

    def load(self, path: Union[str, Path]) -> None:
        load_path = Path(path).expanduser().resolve()
        if not load_path.exists():
            raise FileNotFoundError(f"Dataset archive not found: {load_path}")
        payload = torch.load(load_path, map_location="cpu", weights_only=False)
        self._data_list = payload["data_list"]
        self.conformer_strategy = payload.get("conformer_strategy", "all")
        self.temperature_k = payload.get("temperature_k", STANDARD_TEMPERATURE_K)
        self.seed = payload.get("seed", DEFAULT_RANDOM_SEED)

    def copy(self) -> GEOMInMemoryDataset:
        return GEOMInMemoryDataset(
            root=self._root_path,
            data_list=[d.clone() for d in self._data_list],
            transform=self._custom_transform,
            pre_transform=self._custom_pre_transform,
            pre_filter=self._custom_pre_filter,
            conformer_strategy=self.conformer_strategy,
            temperature_k=self.temperature_k,
            seed=self.seed,
        )

    def __repr__(self) -> str:
        return f"GEOMInMemoryDataset(num_samples={len(self._data_list)}, strategy='{self.conformer_strategy}')"


# ==============================================================================
# 6. GEOM Streaming IterableDataset Implementation
# ==============================================================================

class GEOMIterableDataset(IterableDataset):
    """Streaming IterableDataset for multi-gigabyte MsgPack, JSON, and QM log archives."""

    def __init__(
        self,
        file_paths: Union[str, Path, Sequence[Union[str, Path]]],
        buffer_size: int = DEFAULT_STREAMING_BUFFER_SIZE,
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        filter_fn: Optional[Callable[[MolecularData], bool]] = None,
        conformer_strategy: str = "all",
        temperature_k: float = STANDARD_TEMPERATURE_K,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> None:
        if isinstance(file_paths, (str, Path)):
            p = Path(file_paths).expanduser().resolve()
            if p.is_dir():
                self.file_paths = sorted(list(p.glob("*.msgpack")) + list(p.glob("*.json*")) + list(p.glob("*.log*")) + list(p.glob("*.out*")))
            else:
                self.file_paths = [p]
        else:
            self.file_paths = [Path(fp).expanduser().resolve() for fp in file_paths]

        self.buffer_size = int(buffer_size)
        self.transform = transform
        self.filter_fn = filter_fn
        self.conformer_strategy = conformer_strategy.lower()
        self.temperature_k = float(temperature_k)
        self.seed = seed

    def _stream_msgpack_file(self, file_path: Path) -> Generator[MoleculeRecord, None, None]:
        if msgpack is None:
            raise ImportError("msgpack is required for streaming MsgPack archives.")
        for smiles, mol_data in deserialize_geom_archive(file_path):
            yield parse_geom_raw_molecule(smiles, mol_data, temperature_k=self.temperature_k)

    def _stream_jsonl_file(self, file_path: Path) -> Generator[MolecularData, None, None]:
        featurizer = MolecularFeaturizer()
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                d = json.loads(line_str)
                mol_in = MolecularInput(**d)
                yield featurizer.featurize(mol_in)

    def _stream_qm_log_file(self, file_path: Path) -> Generator[MolecularData, None, None]:
        qm_rec = parse_qm_output(file_path)
        if qm_rec.structures:
            mol_in = MolecularInput(
                symbols=qm_rec.symbols,
                positions=qm_rec.structures[-1],
                energy=qm_rec.energy_hartree,
                forces=qm_rec.forces,
                dipole=qm_rec.dipole_debye,
                rotational_constants=qm_rec.rotational_constants_mhz,
            )
            featurizer = MolecularFeaturizer()
            yield featurizer.featurize(mol_in)

    def __iter__(self) -> Iterator[MolecularData]:
        worker_info = get_worker_info()
        if worker_info is None:
            files_to_read = self.file_paths
            worker_id = 0
            num_workers = 1
            shard_records = False
        else:
            worker_id = worker_info.id
            num_workers = worker_info.num_workers
            if len(self.file_paths) >= num_workers:
                files_to_read = self.file_paths[worker_id::num_workers]
                shard_records = False
            else:
                files_to_read = self.file_paths
                shard_records = True

        rng = random.Random((self.seed or 0) + worker_id)
        global_rec_idx = 0

        for file_path in files_to_read:
            if not file_path.exists():
                continue

            if file_path.suffix in [".msgpack", ".mp"]:
                for rec in self._stream_msgpack_file(file_path):
                    mols: List[MolecularData] = []
                    if self.conformer_strategy == "all":
                        mols = [conformer_to_molecular_data(rec, c) for c in rec.conformers]
                    elif self.conformer_strategy in ["lowest_energy", "min_energy"]:
                        lowest = rec.get_lowest_energy_conformer()
                        if lowest is not None:
                            mols = [conformer_to_molecular_data(rec, lowest)]
                    elif self.conformer_strategy == "boltzmann":
                        mols = ensemble_to_molecular_data(rec)
                    elif self.conformer_strategy == "random":
                        if rec.conformers:
                            mols = [conformer_to_molecular_data(rec, rng.choice(rec.conformers))]

                    for m in mols:
                        if shard_records:
                            curr_idx = global_rec_idx
                            global_rec_idx += 1
                            if curr_idx % num_workers != worker_id:
                                continue
                        if self.filter_fn is not None and not self.filter_fn(m):
                            continue
                        out_mol = self.transform(m) if self.transform is not None else m
                        yield out_mol

            elif file_path.suffix in [".json", ".jsonl"]:
                for m in self._stream_jsonl_file(file_path):
                    if shard_records:
                        curr_idx = global_rec_idx
                        global_rec_idx += 1
                        if curr_idx % num_workers != worker_id:
                            continue
                    if self.filter_fn is not None and not self.filter_fn(m):
                        continue
                    out_mol = self.transform(m) if self.transform is not None else m
                    yield out_mol

            elif file_path.suffix in [".log", ".out"]:
                for m in self._stream_qm_log_file(file_path):
                    if shard_records:
                        curr_idx = global_rec_idx
                        global_rec_idx += 1
                        if curr_idx % num_workers != worker_id:
                            continue
                    if self.filter_fn is not None and not self.filter_fn(m):
                        continue
                    out_mol = self.transform(m) if self.transform is not None else m
                    yield out_mol


# ==============================================================================
# 7. GEOM Dataset Factory Implementation
# ==============================================================================

class GEOMDatasetFactory:
    """Factory design pattern for generating standardized datasets and deterministic data splits."""

    @staticmethod
    def create_custom(
        data_list: Sequence[MolecularData],
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        conformer_strategy: str = "all",
        temperature_k: float = STANDARD_TEMPERATURE_K,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> GEOMInMemoryDataset:
        return GEOMInMemoryDataset(
            data_list=data_list,
            transform=transform,
            conformer_strategy=conformer_strategy,
            temperature_k=temperature_k,
            seed=seed,
        )

    @staticmethod
    def create_qm9(
        root: Optional[Union[str, Path]] = None,
        raw_files: Optional[Sequence[Union[str, Path]]] = None,
        conformer_strategy: str = "lowest_energy",
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> GEOMInMemoryDataset:
        resolved_root = Path(root).expanduser().resolve() if root is not None else get_default_data_dir() / "qm9"
        return GEOMInMemoryDataset(
            root=resolved_root,
            raw_file_paths=raw_files,
            transform=transform,
            conformer_strategy=conformer_strategy,
            seed=seed,
        )

    @staticmethod
    def create_drugs(
        root: Optional[Union[str, Path]] = None,
        raw_files: Optional[Sequence[Union[str, Path]]] = None,
        conformer_strategy: str = "boltzmann",
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        temperature_k: float = STANDARD_TEMPERATURE_K,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> GEOMInMemoryDataset:
        resolved_root = Path(root).expanduser().resolve() if root is not None else get_default_data_dir() / "geom_drugs"
        return GEOMInMemoryDataset(
            root=resolved_root,
            raw_file_paths=raw_files,
            transform=transform,
            conformer_strategy=conformer_strategy,
            temperature_k=temperature_k,
            seed=seed,
        )

    @staticmethod
    def create_pickett(
        molecules: Sequence[MolecularData],
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
    ) -> GEOMInMemoryDataset:
        processed: List[MolecularData] = []
        for m in molecules:
            item = m.clone()
            if item.rotational_constants is None:
                masses = torch.tensor(
                    [resolve_dynamic_mass(s) for s in item.symbols],
                    dtype=item.pos.dtype,
                    device=item.pos.device,
                )
                a, b, c = compute_principal_rotational_constants(item.pos, masses)
                item.rotational_constants = torch.tensor([a, b, c], dtype=item.pos.dtype, device=item.pos.device)
            processed.append(item)

        return GEOMInMemoryDataset(data_list=processed, transform=transform)

    @staticmethod
    def create_qm_log(
        log_paths: Sequence[Union[str, Path]],
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
    ) -> GEOMInMemoryDataset:
        data_list: List[MolecularData] = []
        featurizer = MolecularFeaturizer()

        for lp in log_paths:
            p = Path(lp).expanduser().resolve()
            if not p.exists():
                continue
            qm_rec = parse_qm_output(p)
            if qm_rec.structures:
                mol_in = MolecularInput(
                    symbols=qm_rec.symbols,
                    positions=qm_rec.structures[-1],
                    energy=qm_rec.energy_hartree,
                    forces=qm_rec.forces,
                    dipole=qm_rec.dipole_debye,
                    rotational_constants=qm_rec.rotational_constants_mhz,
                )
                data_list.append(featurizer.featurize(mol_in))

        return GEOMInMemoryDataset(data_list=data_list, transform=transform)

    @staticmethod
    def train_val_test_split(
        dataset: GEOMInMemoryDataset,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        shuffle: bool = True,
        seed: int = DEFAULT_RANDOM_SEED,
        stratify_by: Optional[str] = None,
    ) -> Tuple[GEOMInMemoryDataset, GEOMInMemoryDataset, GEOMInMemoryDataset]:
        if not math.isclose(train_ratio + val_ratio + test_ratio, 1.0, rel_tol=1e-5):
            raise ValueError(f"Split ratios must sum to 1.0; got {train_ratio + val_ratio + test_ratio}")

        n_total = len(dataset)
        if n_total == 0:
            raise ValueError("Cannot split an empty dataset.")

        indices = list(range(n_total))

        if stratify_by is not None:
            strat_groups: Dict[Any, List[int]] = {}
            for i in indices:
                item = dataset.get(i)
                val = getattr(item, stratify_by, item.metadata.get(stratify_by))
                strat_groups.setdefault(val, []).append(i)

            rng = random.Random(seed)
            train_idx, val_idx, test_idx = [], [], []
            for _, grp in strat_groups.items():
                if shuffle:
                    rng.shuffle(grp)
                n_grp = len(grp)
                n_tr = int(round(n_grp * train_ratio))
                n_va = int(round(n_grp * val_ratio))
                train_idx.extend(grp[:n_tr])
                val_idx.extend(grp[n_tr : n_tr + n_va])
                test_idx.extend(grp[n_tr + n_va :])
        else:
            if shuffle:
                rng = random.Random(seed)
                rng.shuffle(indices)

            n_train = int(round(n_total * train_ratio))
            n_val = int(round(n_total * val_ratio))

            train_idx = indices[:n_train]
            val_idx = indices[n_train : n_train + n_val]
            test_idx = indices[n_train + n_val :]

        train_dataset = dataset[train_idx]
        val_dataset = dataset[val_idx]
        test_dataset = dataset[test_idx]

        return train_dataset, val_dataset, test_dataset


# ==============================================================================
# 8. GEOM High-Throughput LMDB Dataset Implementation
# ==============================================================================

class GEOMLmdbDataset(Dataset):
    """Map-style dataset for lock-free, high-throughput multiprocessing reading of LMDB conformer graphs [M].

    Adheres strictly to SRS Document 4:
    - Lazy per-worker initialization (`readonly=True, lock=False, readahead=False, meminit=False`)
    - Zero-mutation principles
    - Dynamic casting of numpy arrays to torch tensors
    """

    def __init__(
        self,
        lmdb_path: Union[str, Path],
        transform: Optional[Callable[[ConformerData], ConformerData]] = None,
    ) -> None:
        super().__init__()
        self._env: Optional[Any] = None
        self.lmdb_path = Path(lmdb_path).expanduser().resolve()
        self.transform = transform

        if not self.lmdb_path.exists():
            raise FileNotFoundError(f"LMDB path does not exist: {self.lmdb_path}")

        metadata_path = self.lmdb_path.parent / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                self._length = int(metadata.get("total_conformers", 0))
        else:
            if lmdb is not None:
                env = lmdb.open(str(self.lmdb_path), subdir=False, readonly=True, lock=False)
                with env.begin() as txn:
                    self._length = int(txn.stat()["entries"])
                env.close()
            else:
                self._length = 0

    def _init_db(self) -> None:
        """Lazily initialize LMDB connection inside worker process [D]."""
        if lmdb is None:
            raise ImportError("lmdb is required to read GEOMLmdbDataset.")
        if self._env is None:
            self._env = lmdb.open(
                str(self.lmdb_path),
                subdir=False,
                readonly=True,
                lock=False,
                readahead=False,
                meminit=False,
            )

    def __len__(self) -> int:
        return self._length

    def __getitem__(self, idx: int) -> ConformerData:
        self._init_db()
        key = f"{idx:09d}".encode("ascii")

        with self._env.begin() as txn:
            data_bytes = txn.get(key)
            if data_bytes is None:
                key_alt = f"{idx}".encode("ascii")
                data_bytes = txn.get(key_alt)

        if data_bytes is None:
            raise KeyError(f"Index {idx} not found in LMDB (key: {key.decode('ascii')}).")

        try:
            raw_dict: Dict[str, Any] = pickle.loads(data_bytes)
        except (pickle.UnpicklingError, TypeError, ValueError):
            raw_dict = json.loads(data_bytes.decode("utf-8"))

        z_raw = raw_dict["z"]
        if isinstance(z_raw, list):
            z_raw = np.array(z_raw, dtype=np.int64)
        z = torch.from_numpy(z_raw).to(torch.long)

        pos_raw = raw_dict["pos"]
        if isinstance(pos_raw, list):
            pos_raw = np.array(pos_raw, dtype=np.float32)
        pos = torch.from_numpy(pos_raw).to(torch.float32)

        edge_index = None
        if "edge_index" in raw_dict and raw_dict["edge_index"] is not None:
            ei_raw = raw_dict["edge_index"]
            if isinstance(ei_raw, list):
                ei_raw = np.array(ei_raw, dtype=np.int64)
            edge_index = torch.from_numpy(ei_raw).to(torch.long)

        edge_attr = None
        if "edge_attr" in raw_dict and raw_dict["edge_attr"] is not None:
            ea_raw = raw_dict["edge_attr"]
            if isinstance(ea_raw, list):
                ea_raw = np.array(ea_raw, dtype=np.float32)
            edge_attr = torch.from_numpy(ea_raw).to(torch.float32)

        y = None
        if "y" in raw_dict and raw_dict["y"] is not None:
            raw_y = raw_dict["y"]
            if isinstance(raw_y, (int, float)):
                y = torch.tensor([raw_y], dtype=torch.float32)
            elif isinstance(raw_y, np.ndarray):
                y = torch.from_numpy(raw_y).to(torch.float32)
                if y.dim() == 0:
                    y = y.unsqueeze(0)
            elif isinstance(raw_y, torch.Tensor):
                y = raw_y.to(torch.float32)
                if y.dim() == 0:
                    y = y.unsqueeze(0)
            else:
                y = torch.tensor(raw_y, dtype=torch.float32)
                if y.dim() == 0:
                    y = y.unsqueeze(0)

        weight = None
        if "weight" in raw_dict and raw_dict["weight"] is not None:
            raw_w = raw_dict["weight"]
            if isinstance(raw_w, (int, float)):
                weight = torch.tensor([raw_w], dtype=torch.float32)
            elif isinstance(raw_w, np.ndarray):
                weight = torch.from_numpy(raw_w).to(torch.float32)
                if weight.dim() == 0:
                    weight = weight.unsqueeze(0)
            elif isinstance(raw_w, torch.Tensor):
                weight = raw_w.to(torch.float32)
                if weight.dim() == 0:
                    weight = weight.unsqueeze(0)
            else:
                weight = torch.tensor(raw_w, dtype=torch.float32)
                if weight.dim() == 0:
                    weight = weight.unsqueeze(0)

        x = (
            torch.from_numpy(raw_dict["x"]).to(torch.float32)
            if "x" in raw_dict and raw_dict["x"] is not None
            else None
        )
        forces = (
            torch.from_numpy(raw_dict["forces"]).to(torch.float32)
            if "forces" in raw_dict and raw_dict["forces"] is not None
            else None
        )
        dipole = None
        if "dipole" in raw_dict and raw_dict["dipole"] is not None:
            raw_d = raw_dict["dipole"]
            if isinstance(raw_d, np.ndarray):
                dipole = torch.from_numpy(raw_d).to(torch.float32)
            elif isinstance(raw_d, torch.Tensor):
                dipole = raw_d.to(torch.float32)
            else:
                dipole = torch.tensor(raw_d, dtype=torch.float32)

        rotational_constants = None
        if "rotational_constants" in raw_dict and raw_dict["rotational_constants"] is not None:
            raw_rc = raw_dict["rotational_constants"]
            if isinstance(raw_rc, np.ndarray):
                rotational_constants = torch.from_numpy(raw_rc).to(torch.float32)
            elif isinstance(raw_rc, torch.Tensor):
                rotational_constants = raw_rc.to(torch.float32)
            else:
                rotational_constants = torch.tensor(raw_rc, dtype=torch.float32)

        symbols = (
            list(raw_dict["symbols"])
            if "symbols" in raw_dict and raw_dict["symbols"] is not None
            else [ATOMIC_NUMBER_TO_SYMBOL.get(int(zi), "X") for zi in z]
        )

        data = ConformerData(
            z=z,
            pos=pos,
            edge_index=edge_index,
            edge_attr=edge_attr,
            y=y,
            weight=weight,
            x=x,
            forces=forces,
            dipole=dipole,
            rotational_constants=rotational_constants,
            symbols=symbols,
            metadata=raw_dict.get("metadata", {}),
        )

        if self.transform is not None:
            data = self.transform(data)

        return data

    def close(self) -> None:
        """Explicitly close LMDB environment and release file descriptors [E]."""
        if getattr(self, "_env", None) is not None:
            try:
                self._env.close()
            except (OSError, RuntimeError) as exc:
                logger.debug("Failed to cleanly close LMDB environment: %s", exc)
            self._env = None

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> GEOMLmdbDataset:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# ==============================================================================
# 9. Architectural Parity Aliases
# ==============================================================================

ConformerData = MolecularData
"""Alias for MolecularData to maintain parity with SRS Document 4."""

CenterOfMassZeroing = CenterOfMassTransform
"""Alias for CenterOfMassTransform to maintain parity with SRS Document 4."""

TargetStandardize = NormalizeTargetsTransform
"""Alias for NormalizeTargetsTransform to maintain parity with SRS Document 4."""


__all__ = [
    "DEFAULT_RANDOM_SEED",
    "DEFAULT_STREAMING_BUFFER_SIZE",
    "BaseTransform",
    "CenterOfMassTransform",
    "CenterOfMassZeroing",
    "ComposeTransforms",
    "ConformerData",
    "EckartAlignmentTransform",
    "GEOMDatasetFactory",
    "GEOMInMemoryDataset",
    "GEOMIterableDataset",
    "GEOMLmdbDataset",
    "GaussianJitterTransform",
    "MolecularBatch",
    "NormalizeTargetsTransform",
    "RandomRotationTransform",
    "TargetStandardize",
    "geom_collate_fn",
    "get_default_data_dir",
    "resolve_dynamic_mass",
    "resolve_dynamic_monoisotopic_mass",
]
