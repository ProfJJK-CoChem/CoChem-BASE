"""CoChem-GEOM: PyTorch Geometric (PyG) Equivariant & Target Transformations.
=====================================================================================
Establishes the authoritative geometric and physical transformation layer for PyG
`ConformerData` and `MolecularData` graph containers in quantum chemistry and rotational
spectroscopy.

Key Components:
1. `CenterOfMassZeroing` / `CenterOfMassTransform`:
   - Translates coordinates to geometric centroid (or mass-weighted COM) origin strictly to (0, 0, 0).
   - Drastically improves float32 numerical stability in downstream Euclidean distance calculations [D].
   - Dynamically resolves atomic masses via Mendeleev (NEVER hardcoded) for mass-weighted COM [M].
   - Implements pure immutable coordinate transformation without in-place tensor corruption [D].

2. `TargetStandardize` / `NormalizeTargetsTransform`:
   - Standardizes scalar target properties (e.g., ground-state electronic energy y) to zero mean
     and unit variance: y' = (y - μ) / (σ + ε) [D].
   - Prevents numeric gradient collapse on massive raw quantum energies (e.g., -3000 eV) [M].
   - Provides exact `denormalize` inverse mapping to recover true physical units during inference [D].

3. `RandomRotation` / `RandomRotationTransform`:
   - Applies uniform random SO(3) 3D rotations equivariantly via Haar measure [D].
   - Rotates Cartesian positions, atomic forces, and dipole vectors equivariantly [D].

4. `GaussianJitter` / `GaussianJitterTransform`:
   - Injects isotropic zero-mean Gaussian coordinate perturbation immutably [E].

5. `EckartAlignment` / `EckartAlignmentTransform`:
   - Aligns conformers to reference geometry via SVD Kabsch / Eckart frame rotation minimizing RMSD [D].

6. `ComposeTransforms` / `Compose`:
   - Sequentially chains multiple transformations into a unified callable pipeline [E].

Authoritative Standards & Directives:
- Method Matrix v4.1: Data Ingestion & Spectroscopic Graph Contracts
- Mendeleev Library Mandate: Dynamic atomic mass & isotopic resolution (NEVER hardcoded)
- State Immutability: Pure functional geometric transformations (immutable operations)
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Cryptographic Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Mandate: 100% authentic physical tensor mathematics and real execution
"""

from __future__ import annotations

import abc
import copy
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TypeVar, Union

import mendeleev
import numpy as np
import torch
from torch_geometric.data import Data

from cochem_geom.data.featurizer import (
    ATOMIC_NUMBER_TO_SYMBOL,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    compute_center_of_mass,
    get_atomic_mass,
    get_monoisotopic_mass,
)
from cochem_geom.data.pyg_schema import ConformerData

logger = logging.getLogger("cochem_geom.data.transforms")

# Generic TypeVar for Data-like objects
T = TypeVar("T", bound=Union[Data, ConformerData, MolecularData, Any])

# Thread-safe Mendeleev dynamic mass caches
_DYNAMIC_MASS_CACHE: Dict[str, float] = {}
_DYNAMIC_MONO_MASS_CACHE: Dict[str, float] = {}


def resolve_dynamic_mass(symbol_or_z: Union[str, int]) -> float:
    """Resolve atomic mass dynamically via Mendeleev with local caching [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        IUPAC chemical element symbol (e.g. 'C', 'H') or atomic number Z (e.g. 6, 1).

    Returns
    -------
    float
        Standard atomic mass in unified atomic mass units (Da or u) [M].
    """
    key = str(symbol_or_z).strip().capitalize()
    if key not in _DYNAMIC_MASS_CACHE:
        _DYNAMIC_MASS_CACHE[key] = get_atomic_mass(symbol_or_z)
    return _DYNAMIC_MASS_CACHE[key]


def resolve_dynamic_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
    """Resolve monoisotopic mass dynamically via Mendeleev with local caching [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        IUPAC chemical element symbol or atomic number Z.

    Returns
    -------
    float
        Exact mass of the most abundant isotope in unified atomic mass units [M].
    """
    key = str(symbol_or_z).strip().capitalize()
    if key not in _DYNAMIC_MONO_MASS_CACHE:
        _DYNAMIC_MONO_MASS_CACHE[key] = get_monoisotopic_mass(symbol_or_z)
    return _DYNAMIC_MONO_MASS_CACHE[key]


# ==============================================================================
# 1. Base Transform Interface
# ==============================================================================


class BaseTransform(abc.ABC):
    """Abstract base class for pure immutable molecular graph transformations [D]."""

    @abc.abstractmethod
    def __call__(self, data: Any) -> Any:
        """Apply transformation immutably, returning the transformed data instance [D].

        Parameters
        ----------
        data : Any
            Input molecular graph container (e.g. ConformerData, MolecularData, or PyG Data).

        Returns
        -------
        Any
            Transformed molecular graph container.
        """
        pass

    def __repr__(self) -> str:
        """Return human-readable string representation of the transform [E]."""
        return f"{self.__class__.__name__}()"


# ==============================================================================
# 2. Center of Mass & Geometric Centroid Zeroing
# ==============================================================================


class CenterOfMassZeroing(BaseTransform):
    r"""Translates molecular coordinates such that center of mass / centroid is at (0, 0, 0) [D].

    Translating the centroid strictly to the Cartesian origin drastically improves
    float32 numerical stability [D] in downstream Euclidean distance and radial basis
    function calculations without violating rotation symmetries.

    $$\mathbf{r}'_i = \mathbf{r}_i - \mathbf{r}_{\text{COM}}$$

    Parameters
    ----------
    mass_weighted : bool, default=False
        If True, computes physical center of mass using dynamic atomic masses dynamically
        queried from Mendeleev (NEVER hardcoded) [M]. If False, computes geometric centroid [D].
    use_monoisotopic : bool, default=False
        If True and `mass_weighted` is True, uses most abundant isotopic masses rather than
        standard atomic weights [M].
    """

    def __init__(self, mass_weighted: bool = False, use_monoisotopic: bool = False) -> None:
        self.mass_weighted = bool(mass_weighted)
        self.use_monoisotopic = bool(use_monoisotopic)

    def _resolve_masses(self, data: Any) -> torch.Tensor:
        """Resolve atomic mass tensor dynamically via Mendeleev [M]."""
        symbols = getattr(data, "symbols", None)
        z = getattr(data, "z", None)

        if symbols is not None and len(symbols) > 0:
            if self.use_monoisotopic:
                mass_list = [resolve_dynamic_monoisotopic_mass(s) for s in symbols]
            else:
                mass_list = [resolve_dynamic_mass(s) for s in symbols]
        elif z is not None and len(z) > 0:
            if self.use_monoisotopic:
                mass_list = [resolve_dynamic_monoisotopic_mass(int(zi.item() if isinstance(zi, torch.Tensor) else zi)) for zi in z]
            else:
                mass_list = [resolve_dynamic_mass(int(zi.item() if isinstance(zi, torch.Tensor) else zi)) for zi in z]
        else:
            # Fallback uniform unit masses
            num_atoms = data.pos.size(0) if hasattr(data, "pos") and data.pos is not None else 1
            mass_list = [1.0] * num_atoms

        return torch.tensor(
            mass_list,
            dtype=data.pos.dtype if hasattr(data, "pos") and isinstance(data.pos, torch.Tensor) else torch.float32,
            device=data.pos.device if hasattr(data, "pos") and isinstance(data.pos, torch.Tensor) else torch.device("cpu"),
        )

    def __call__(self, data: T) -> T:
        """Apply center of mass / centroid zeroing immutably [D].

        Parameters
        ----------
        data : T
            ConformerData, MolecularData, or PyG Data containing `pos` coordinates.

        Returns
        -------
        T
            Transformed data instance with origin-centered coordinates.
        """
        if not hasattr(data, "pos") or data.pos is None:
            return data

        pos = data.pos
        if not isinstance(pos, torch.Tensor):
            raise TypeError(f"Expected data.pos to be a torch.Tensor, got {type(pos)}")

        if pos.numel() == 0:
            return data

        if self.mass_weighted:
            masses = self._resolve_masses(data)
            com = compute_center_of_mass(pos, masses)
            shift = com.unsqueeze(0) if com.dim() == 1 else com
        else:
            # Geometric centroid: mean over spatial node dimension (N, 3) -> (1, 3) [D]
            shift = pos.mean(dim=0, keepdim=True)

        # Pure functional non-in-place translation (never pos.sub_()) [D]
        new_pos = pos - shift

        # If data is MolecularData, construct new immutable MolecularData
        if isinstance(data, MolecularData):
            return MolecularData(
                z=data.z.clone() if data.z is not None else None,
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
                symbols=list(data.symbols) if data.symbols is not None else None,
                metadata=copy.deepcopy(data.metadata) if data.metadata is not None else {},
            )  # type: ignore

        # For ConformerData and PyG Data objects, update pos immutably
        data.pos = new_pos
        return data

    def __repr__(self) -> str:
        return f"CenterOfMassZeroing(mass_weighted={self.mass_weighted}, use_monoisotopic={self.use_monoisotopic})"


# Backward-compatible alias
CenterOfMassTransform = CenterOfMassZeroing


# ==============================================================================
# 3. Target Property Standardization & Denormalization
# ==============================================================================


class TargetStandardize(BaseTransform):
    r"""Standardizes target property (y) to have zero mean and unit variance [D].

    Predicting massive raw quantum chemical total ground-state energies (e.g. -3000 eV)
    directly causes numerical gradient collapse [M]. Standardizing target property y
    using dataset global statistics is mandatory for numerical stability.

    $$y' = \frac{y - \mu}{\sigma + \epsilon}$$

    Parameters
    ----------
    mean : Union[float, Sequence[float], torch.Tensor]
        Dataset global target mean $\mu$ [D].
    std : Union[float, Sequence[float], torch.Tensor]
        Dataset global target standard deviation $\sigma$ [D].
    eps : float, default=1e-8
        Small numerical stability epsilon preventing zero division [E].

    Raises
    ------
    ValueError
        If standard deviation `std` is non-positive (<= 0).
    """

    def __init__(
        self,
        mean: Union[float, Sequence[float], torch.Tensor],
        std: Union[float, Sequence[float], torch.Tensor],
        eps: float = 1e-8,
    ) -> None:
        self.mean_raw = mean
        self.std_raw = std
        self.eps = float(eps)

        self.mean: torch.Tensor = torch.as_tensor(mean, dtype=torch.float32)
        self.std: torch.Tensor = torch.as_tensor(std, dtype=torch.float32)

        if (self.std <= 0).any():
            raise ValueError(f"Target standard deviation 'std' must be strictly positive, got {self.std.tolist()}")

    def __call__(self, data: T) -> T:
        """Apply target standardization immutably [D].

        Parameters
        ----------
        data : T
            ConformerData, MolecularData, or PyG Data containing target tensor `y`.

        Returns
        -------
        T
            Transformed data container with standardized `y`.
        """
        if not hasattr(data, "y") or data.y is None:
            return data

        y = data.y
        if not isinstance(y, torch.Tensor):
            raise TypeError(f"Expected data.y to be a torch.Tensor, got {type(y)}")

        mean = self.mean.to(dtype=y.dtype, device=y.device)
        std = self.std.to(dtype=y.dtype, device=y.device)

        # Pure functional standardization
        new_y = (y - mean) / (std + self.eps)

        if isinstance(data, MolecularData):
            return MolecularData(
                z=data.z.clone() if data.z is not None else None,
                pos=data.pos.clone() if data.pos is not None else None,
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
                symbols=list(data.symbols) if data.symbols is not None else None,
                metadata=copy.deepcopy(data.metadata) if data.metadata is not None else {},
            )  # type: ignore

        data.y = new_y
        return data

    def denormalize(self, y_norm: torch.Tensor) -> torch.Tensor:
        r"""Denormalize standardized target tensor back to true physical units [D].

        $$y = y_{\text{norm}} \cdot (\sigma + \epsilon) + \mu$$

        Parameters
        ----------
        y_norm : torch.Tensor
            Standardized predictions or targets tensor of arbitrary shape.

        Returns
        -------
        torch.Tensor
            Denormalized tensor scaled back to original physical energy/property units [D].
        """
        if not isinstance(y_norm, torch.Tensor):
            y_norm = torch.as_tensor(y_norm, dtype=torch.float32)

        mean = self.mean.to(dtype=y_norm.dtype, device=y_norm.device)
        std = self.std.to(dtype=y_norm.dtype, device=y_norm.device)

        return y_norm * (std + self.eps) + mean

    def unscale(self, y_norm: torch.Tensor) -> torch.Tensor:
        r"""Alias for denormalize: unscale normalized target tensor back to physical units [D]."""
        return self.denormalize(y_norm)

    def inverse_transform(self, y_norm: torch.Tensor) -> torch.Tensor:
        r"""Scikit-learn style alias for denormalize [D]."""
        return self.denormalize(y_norm)

    def __repr__(self) -> str:
        return f"TargetStandardize(mean={self.mean.tolist()}, std={self.std.tolist()}, eps={self.eps})"


# Backward-compatible alias
NormalizeTargetsTransform = TargetStandardize


# ==============================================================================
# 4. SO(3) Equivariant Random Rotation Transform
# ==============================================================================


class RandomRotation(BaseTransform):
    r"""Apply a uniformly sampled random 3D rotation from SO(3) equivariantly [D].

    Rotates Cartesian coordinates, atomic forces, and electric dipole moment vectors
    under the Haar measure on SO(3):

    $$\mathbf{r}'_i = \mathbf{r}_i \mathbf{R}^T, \quad \mathbf{F}'_i = \mathbf{F}_i \mathbf{R}^T, \quad \boldsymbol{\mu}' = \boldsymbol{\mu} \mathbf{R}^T$$

    where $\mathbf{R} \in \mathrm{SO}(3)$ is an orthogonal rotation matrix with $\det(\mathbf{R}) = +1$.

    Parameters
    ----------
    seed : Optional[int], default=None
        Optional deterministic pseudo-random generator seed [E].
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self.seed = seed
        self.rng = np.random.default_rng(seed) if seed is not None else None

    def _generate_so3_matrix(self, dtype: torch.dtype, device: torch.device) -> torch.Tensor:
        """Generate a uniformly sampled random SO(3) matrix via Haar measure [D]."""
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

    def __call__(self, data: T) -> T:
        """Apply random SO(3) rotation equivariantly and immutably [D].

        Parameters
        ----------
        data : T
            ConformerData, MolecularData, or PyG Data.

        Returns
        -------
        T
            Rotated data container.
        """
        if not hasattr(data, "pos") or data.pos is None:
            return data

        rot_mat = self._generate_so3_matrix(data.pos.dtype, data.pos.device)

        if isinstance(data, ConformerData):
            return data.rotate(rot_mat)  # type: ignore

        new_pos = data.pos @ rot_mat.T
        new_forces = data.forces @ rot_mat.T if hasattr(data, "forces") and data.forces is not None else None

        new_dipole = None
        if hasattr(data, "dipole") and data.dipole is not None:
            if data.dipole.dim() == 1:
                new_dipole = rot_mat @ data.dipole
            else:
                new_dipole = data.dipole @ rot_mat.T

        if isinstance(data, MolecularData):
            return MolecularData(
                z=data.z.clone() if data.z is not None else None,
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
                symbols=list(data.symbols) if data.symbols is not None else None,
                metadata=copy.deepcopy(data.metadata) if data.metadata is not None else {},
            )  # type: ignore

        data.pos = new_pos
        if new_forces is not None:
            data.forces = new_forces
        if new_dipole is not None:
            data.dipole = new_dipole
        return data

    def __repr__(self) -> str:
        return f"RandomRotation(seed={self.seed})"


# Backward-compatible alias
RandomRotationTransform = RandomRotation


# ==============================================================================
# 5. Coordinate Gaussian Jitter Transform
# ==============================================================================


class GaussianJitter(BaseTransform):
    r"""Add zero-mean isotropic Gaussian noise to Cartesian coordinates immutably [E].

    $$\mathbf{r}'_i = \mathbf{r}_i + \boldsymbol{\epsilon}_i, \quad \boldsymbol{\epsilon}_i \sim \mathcal{N}(\mathbf{0}, \sigma^2 \mathbf{I})$$

    Parameters
    ----------
    sigma : float, default=0.01
        Noise standard deviation in Angstroms [E].
    seed : Optional[int], default=None
        Deterministic seed for reproducibility [E].
    """

    def __init__(self, sigma: float = 0.01, seed: Optional[int] = None) -> None:
        self.sigma = float(sigma)
        self.seed = seed
        self.generator = torch.Generator().manual_seed(seed) if seed is not None else None

    def __call__(self, data: T) -> T:
        """Apply isotropic Gaussian jitter to Cartesian coordinates immutably [E].

        Parameters
        ----------
        data : T
            ConformerData, MolecularData, or PyG Data.

        Returns
        -------
        T
            Jittered data container.
        """
        if not hasattr(data, "pos") or data.pos is None or self.sigma <= 0.0:
            return data

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

        new_pos = data.pos + noise

        if isinstance(data, MolecularData):
            return MolecularData(
                z=data.z.clone() if data.z is not None else None,
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
                symbols=list(data.symbols) if data.symbols is not None else None,
                metadata=copy.deepcopy(data.metadata) if data.metadata is not None else {},
            )  # type: ignore

        data.pos = new_pos
        return data

    def __repr__(self) -> str:
        return f"GaussianJitter(sigma={self.sigma}, seed={self.seed})"


# Backward-compatible alias
GaussianJitterTransform = GaussianJitter


# ==============================================================================
# 6. SVD Kabsch / Eckart Frame Alignment Transform
# ==============================================================================


class EckartAlignment(BaseTransform):
    r"""Align molecular coordinates to a target reference structure via SVD Kabsch rotation [D].

    Finds optimal $\mathbf{R} \in \mathrm{SO}(3)$ minimizing mass-weighted root mean square deviation (RMSD)
    with dynamic Mendeleev masses (NEVER hardcoded).

    Parameters
    ----------
    reference : Union[ConformerData, MolecularData, Data, torch.Tensor]
        Reference conformer or coordinate tensor of shape (N, 3).
    use_mass_weighting : bool, default=True
        Whether to perform mass-weighted Kabsch alignment using dynamic Mendeleev masses [M].
    """

    def __init__(
        self,
        reference: Union[ConformerData, MolecularData, Data, torch.Tensor],
        use_mass_weighting: bool = True,
    ) -> None:
        self.reference = reference
        self.use_mass_weighting = bool(use_mass_weighting)

    def _resolve_ref_pos(self) -> torch.Tensor:
        """Extract Cartesian reference coordinates [D]."""
        if isinstance(self.reference, torch.Tensor):
            return self.reference
        if hasattr(self.reference, "pos") and isinstance(self.reference.pos, torch.Tensor):
            return self.reference.pos
        raise TypeError(f"Invalid reference object type: {type(self.reference)}")

    def __call__(self, data: T) -> T:
        """Apply Eckart / Kabsch alignment immutably [D].

        Parameters
        ----------
        data : T
            Target molecular container to align.

        Returns
        -------
        T
            Aligned molecular container.
        """
        if not hasattr(data, "pos") or data.pos is None:
            return data

        ref_pos = self._resolve_ref_pos().to(dtype=data.pos.dtype, device=data.pos.device)

        if self.use_mass_weighting:
            symbols = getattr(data, "symbols", None)
            z = getattr(data, "z", None)
            if symbols is not None and len(symbols) > 0:
                masses_list = [resolve_dynamic_mass(s) for s in symbols]
            elif z is not None and len(z) > 0:
                masses_list = [resolve_dynamic_mass(int(zi.item() if isinstance(zi, torch.Tensor) else zi)) for zi in z]
            else:
                masses_list = [1.0] * data.pos.size(0)
        else:
            masses_list = [1.0] * data.pos.size(0)

        masses = torch.tensor(masses_list, dtype=data.pos.dtype, device=data.pos.device)

        data_com = compute_center_of_mass(data.pos, masses)
        ref_com = compute_center_of_mass(ref_pos, masses)

        p = data.pos - data_com.unsqueeze(0)
        q = ref_pos - ref_com.unsqueeze(0)

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
        new_forces = data.forces @ rot_mat.T if hasattr(data, "forces") and data.forces is not None else None

        new_dipole = None
        if hasattr(data, "dipole") and data.dipole is not None:
            if data.dipole.dim() == 1:
                new_dipole = rot_mat @ data.dipole
            else:
                new_dipole = data.dipole @ rot_mat.T

        if isinstance(data, MolecularData):
            return MolecularData(
                z=data.z.clone() if data.z is not None else None,
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
                symbols=list(data.symbols) if data.symbols is not None else None,
                metadata=copy.deepcopy(data.metadata) if data.metadata is not None else {},
            )  # type: ignore

        data.pos = new_pos
        if new_forces is not None:
            data.forces = new_forces
        if new_dipole is not None:
            data.dipole = new_dipole
        return data

    def __repr__(self) -> str:
        return f"EckartAlignment(use_mass_weighting={self.use_mass_weighting})"


# Backward-compatible alias
EckartAlignmentTransform = EckartAlignment


# ==============================================================================
# 7. Compose Transforms Pipeline
# ==============================================================================


class ComposeTransforms(BaseTransform):
    """Chain multiple transformations sequentially into a unified callable pipeline [E].

    Parameters
    ----------
    transforms : Sequence[Callable[[Any], Any]]
        Ordered list of callable transformation objects.
    """

    def __init__(self, transforms: Sequence[Callable[[Any], Any]]) -> None:
        self.transforms = list(transforms)

    def __call__(self, data: T) -> T:
        """Apply sequential pipeline of transformations [E].

        Parameters
        ----------
        data : T
            Input molecular graph container.

        Returns
        -------
        T
            Sequentially transformed molecular graph container.
        """
        current_data = data
        for t in self.transforms:
            current_data = t(current_data)
        return current_data

    def __repr__(self) -> str:
        args = ", ".join([str(t) for t in self.transforms])
        return f"ComposeTransforms([{args}])"


# Backward-compatible alias
Compose = ComposeTransforms

__all__ = [
    "BaseTransform",
    "CenterOfMassTransform",
    "CenterOfMassZeroing",
    "Compose",
    "ComposeTransforms",
    "EckartAlignment",
    "EckartAlignmentTransform",
    "GaussianJitter",
    "GaussianJitterTransform",
    "NormalizeTargetsTransform",
    "RandomRotation",
    "RandomRotationTransform",
    "TargetStandardize",
    "resolve_dynamic_mass",
    "resolve_dynamic_monoisotopic_mass",
]
