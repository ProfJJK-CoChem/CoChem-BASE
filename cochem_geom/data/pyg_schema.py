"""CoChem-GEOM: PyTorch Geometric (PyG) Execution Tensor Schema.
=============================================================================
Defines the authoritative `ConformerData` tensor container subclassing
`torch_geometric.data.Data` for rotational spectroscopy, quantum chemistry,
and equivariant neural network architectures (EGNN, SchNet, DimeNet++, PaiNN).

Authoritative Standards:
- Method Matrix v4: Data Ingestion & Spectroscopic Graph Contracts
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Mendeleev Library Mandate: Dynamic atomic mass & isotopic resolution (NEVER hardcoded)
- Cryptographic Provenance: SHA-256 checksum generation for structures and files
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial node features
- State Immutability: Pure functional geometric transformations (immutable operations)
- Strict Zero-Mock Mandate: Authentic physical constants and real quantum chemical geometries
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import torch
from torch_geometric.data import Batch, Data

from cochem_geom.data.featurizer import (
    ATOMIC_NUMBER_TO_SYMBOL,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    build_radius_graph,
    get_atomic_mass,
)
from cochem_geom.data.geom_parser import (
    ConformerRecord,
    compute_file_sha256,
)

logger = logging.getLogger("cochem_geom.data.pyg_schema")


# ==============================================================================
# 1. Validation Helpers and Error Definitions
# ==============================================================================


class SchemaValidationError(ValueError):
    """Raised when tensor shapes, types, or physical constraints are violated."""
    pass


def validate_conformer_data(data: ConformerData) -> None:
    """Perform fail-fast strict validation of ConformerData tensor schema [M]/[D].

    Validation rules:
    - `z`: 1D torch.Tensor of dtype `torch.long` or `torch.int64`, non-empty, non-negative.
    - `pos`: 2D torch.Tensor of shape `(N, 3)` of dtype `torch.float32`. float16/half is rejected.
    - `z.size(0) == pos.size(0)`: Number of atomic centers must match exactly.
    - `edge_index`: 2D torch.Tensor of shape `(2, E)` of dtype `torch.long` or `torch.int64`.
      Indices must satisfy `0 <= edge_index < N`.
    - `y`: Optional torch.Tensor of dtype `torch.float32`.
    - `weight`: Optional torch.Tensor of dtype `torch.float32`.
    - `x`: Optional 2D torch.Tensor of shape `(N, F)` of dtype `torch.float32`.
    - `edge_attr`: Optional 2D torch.Tensor of shape `(E, D)` of dtype `torch.float32`.
    - `forces`: Optional 2D torch.Tensor of shape `(N, 3)` of dtype `torch.float32`.
    - `dipole`: Optional torch.Tensor of shape `(3,)` or `(1, 3)` of dtype `torch.float32`.
    - `rotational_constants`: Optional torch.Tensor of shape `(3,)` or `(1, 3)` of dtype `torch.float32`.

    Parameters
    ----------
    data : ConformerData
        The ConformerData instance to validate.

    Raises
    ------
    TypeError
        If dtypes or non-tensor attributes violate specification.
    ValueError / SchemaValidationError
        If shapes, dimensions, or indexing bounds are invalid.
    """
    if not isinstance(data, (Data, ConformerData)):
        raise TypeError(f"Expected ConformerData or torch_geometric.data.Data, got {type(data)}")

    # 1. Validate z (Atomic Numbers)
    z_val = getattr(data, "z", None)
    if z_val is None:
        raise SchemaValidationError("ConformerData must contain atomic numbers tensor 'z'.")
    if not isinstance(z_val, torch.Tensor):
        raise TypeError(f"Attribute 'z' must be a torch.Tensor, got {type(z_val)}")
    if z_val.dim() != 1:
        raise SchemaValidationError(f"Attribute 'z' must be a 1D tensor of shape (N,), got shape {list(z_val.shape)}")
    if z_val.dtype not in (torch.int64, torch.long, torch.int32):
        raise TypeError(f"Attribute 'z' must have integer dtype (torch.long/int64), got {z_val.dtype}")
    if z_val.numel() == 0:
        raise SchemaValidationError("Attribute 'z' cannot be empty (N >= 1 required).")
    if (z_val <= 0).any():
        raise SchemaValidationError(f"All atomic numbers in 'z' must be positive integers, found <= 0 in {z_val.tolist()}")

    num_atoms = z_val.size(0)

    # 2. Validate pos (Cartesian Coordinates)
    pos_val = getattr(data, "pos", None)
    if pos_val is None:
        raise SchemaValidationError("ConformerData must contain Cartesian coordinates tensor 'pos'.")
    if not isinstance(pos_val, torch.Tensor):
        raise TypeError(f"Attribute 'pos' must be a torch.Tensor, got {type(pos_val)}")
    if pos_val.dtype in (torch.float16, torch.bfloat16):
        raise TypeError(
            f"ConformerData pos does not support reduced precision float16/bfloat16 ({pos_val.dtype}); "
            "float32 is required for physical and rotational coordinate precision."
        )
    if pos_val.dtype != torch.float32:
        raise TypeError(f"Attribute 'pos' must have dtype torch.float32, got {pos_val.dtype}")
    if pos_val.dim() != 2 or pos_val.size(1) != 3:
        raise SchemaValidationError(
            f"Attribute 'pos' must have shape (N, 3), got {list(pos_val.shape)}"
        )
    if pos_val.size(0) != num_atoms:
        raise SchemaValidationError(
            f"Atom count mismatch: z has {num_atoms} atoms but pos has {pos_val.size(0)} coordinates."
        )

    # 3. Validate edge_index (Graph Connectivity)
    edge_index_val = getattr(data, "edge_index", None)
    if edge_index_val is not None:
        if not isinstance(edge_index_val, torch.Tensor):
            raise TypeError(f"Attribute 'edge_index' must be a torch.Tensor, got {type(edge_index_val)}")
        if edge_index_val.dtype not in (torch.int64, torch.long, torch.int32):
            raise TypeError(f"Attribute 'edge_index' must have integer dtype (torch.long), got {edge_index_val.dtype}")
        if edge_index_val.dim() != 2 or edge_index_val.size(0) != 2:
            raise SchemaValidationError(
                f"Attribute 'edge_index' must have shape (2, E), got {list(edge_index_val.shape)}"
            )
        num_edges = edge_index_val.size(1)
        if num_edges > 0 and num_atoms > 0:
            max_idx = int(edge_index_val.max().item())
            min_idx = int(edge_index_val.min().item())
            if min_idx < 0:
                raise SchemaValidationError(f"Attribute 'edge_index' contains negative node index {min_idx}.")
            if max_idx >= num_atoms:
                raise SchemaValidationError(
                    f"Attribute 'edge_index' references node index {max_idx} >= num_atoms ({num_atoms})."
                )
    else:
        num_edges = 0

    # 4. Validate y (Target Property / Energy)
    y_val = getattr(data, "y", None)
    if y_val is not None:
        if not isinstance(y_val, torch.Tensor):
            raise TypeError(f"Attribute 'y' must be a torch.Tensor, got {type(y_val)}")
        if y_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'y' must have dtype torch.float32, got {y_val.dtype}")

    # 5. Validate weight (Statistical / Boltzmann Weight)
    w_val = getattr(data, "weight", None)
    if w_val is not None:
        if not isinstance(w_val, torch.Tensor):
            raise TypeError(f"Attribute 'weight' must be a torch.Tensor, got {type(w_val)}")
        if w_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'weight' must have dtype torch.float32, got {w_val.dtype}")

    # 6. Validate x (Node Invariant Features)
    x_val = getattr(data, "x", None)
    if x_val is not None:
        if not isinstance(x_val, torch.Tensor):
            raise TypeError(f"Attribute 'x' must be a torch.Tensor, got {type(x_val)}")
        if x_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'x' must have dtype torch.float32, got {x_val.dtype}")
        if x_val.dim() != 2 or x_val.size(0) != num_atoms:
            raise SchemaValidationError(
                f"Attribute 'x' must have shape (N, F) where N={num_atoms}, got {list(x_val.shape)}"
            )

    # 7. Validate edge_attr (Edge Feature Tensor)
    ea_val = getattr(data, "edge_attr", None)
    if ea_val is not None:
        if not isinstance(ea_val, torch.Tensor):
            raise TypeError(f"Attribute 'edge_attr' must be a torch.Tensor, got {type(ea_val)}")
        if ea_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'edge_attr' must have dtype torch.float32, got {ea_val.dtype}")
        if ea_val.dim() != 2 or ea_val.size(0) != num_edges:
            raise SchemaValidationError(
                f"Attribute 'edge_attr' must have shape (E, D) where E={num_edges}, got {list(ea_val.shape)}"
            )

    # 8. Validate forces (Cartesian Atomic Forces)
    f_val = getattr(data, "forces", None)
    if f_val is not None:
        if not isinstance(f_val, torch.Tensor):
            raise TypeError(f"Attribute 'forces' must be a torch.Tensor, got {type(f_val)}")
        if f_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'forces' must have dtype torch.float32, got {f_val.dtype}")
        if f_val.dim() != 2 or f_val.shape != pos_val.shape:
            raise SchemaValidationError(
                f"Attribute 'forces' must have shape {list(pos_val.shape)}, got {list(f_val.shape)}"
            )

    # 9. Validate dipole (Electric Dipole Vector)
    d_val = getattr(data, "dipole", None)
    if d_val is not None:
        if not isinstance(d_val, torch.Tensor):
            raise TypeError(f"Attribute 'dipole' must be a torch.Tensor, got {type(d_val)}")
        if d_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'dipole' must have dtype torch.float32, got {d_val.dtype}")
        if not ((d_val.dim() == 1 and d_val.size(0) == 3) or (d_val.dim() == 2 and d_val.shape == (1, 3))):
            raise SchemaValidationError(
                f"Attribute 'dipole' must have shape (3,) or (1, 3), got {list(d_val.shape)}"
            )

    # 10. Validate rotational_constants (A, B, C in MHz)
    rc_val = getattr(data, "rotational_constants", None)
    if rc_val is not None:
        if not isinstance(rc_val, torch.Tensor):
            raise TypeError(f"Attribute 'rotational_constants' must be a torch.Tensor, got {type(rc_val)}")
        if rc_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'rotational_constants' must have dtype torch.float32, got {rc_val.dtype}")
        if not ((rc_val.dim() == 1 and rc_val.size(0) == 3) or (rc_val.dim() == 2 and rc_val.shape == (1, 3))):
            raise SchemaValidationError(
                f"Attribute 'rotational_constants' must have shape (3,) or (1, 3), got {list(rc_val.shape)}"
            )


def is_valid_conformer_data(data: Any) -> bool:
    """Return True if object is a fully valid ConformerData instance, False otherwise.

    Parameters
    ----------
    data : Any
        Object to inspect.

    Returns
    -------
    bool
        True if valid without exception, False otherwise.
    """
    try:
        validate_conformer_data(data)
        return True
    except (SchemaValidationError, TypeError, ValueError, AttributeError):
        return False


# ==============================================================================
# 2. ConformerData Tensor Schema Class
# ==============================================================================


class ConformerData(Data):
    """Authoritative PyTorch Geometric execution tensor container for molecular conformers.

    Inherits from `torch_geometric.data.Data`. Enforces float32 spatial coordinate precision,
    SE(3)-equivariant operations, dynamic Mendeleev mass calculations, and state immutability.

    Attributes
    ----------
    z : torch.Tensor
        Atomic numbers Z of shape (N,) with dtype torch.long.
    pos : torch.Tensor
        Spatial Cartesian coordinates in Angstroms of shape (N, 3) with dtype torch.float32.
    edge_index : torch.Tensor
        Graph connectivity edge indices of shape (2, E) with dtype torch.long.
    y : Optional[torch.Tensor]
        Scalar target ground-state electronic energy of shape (1,) with dtype torch.float32.
    x : Optional[torch.Tensor]
        Non-spatial invariant node features of shape (N, F) with dtype torch.float32.
    edge_attr : Optional[torch.Tensor]
        Edge feature attributes (e.g. RBF distances) of shape (E, D) with dtype torch.float32.
    weight : torch.Tensor
        Statistical or Boltzmann thermodynamic weighting factor of shape (1,) with dtype torch.float32.
    forces : Optional[torch.Tensor]
        Spatial gradient forces of shape (N, 3) with dtype torch.float32.
    dipole : Optional[torch.Tensor]
        Electric dipole moment vector of shape (3,) with dtype torch.float32.
    rotational_constants : Optional[torch.Tensor]
        Principal spectroscopic rotational constants (A, B, C) in MHz of shape (3,) with dtype torch.float32.
    symbols : List[str]
        IUPAC chemical symbols of length N.
    smiles : Optional[str]
        Canonical SMILES string representation.
    conformer_id : Optional[int]
        Sequential conformer index within the molecular ensemble.
    source_hash : Optional[str]
        Cryptographic SHA-256 provenance checksum of the calculation source or file.
    frequencies : Optional[torch.Tensor]
        Harmonic vibrational frequencies in cm^-1 of shape (M,) with dtype torch.float32.
    s2_spin : Optional[float]
        Spin angular momentum expectation value <S^2>.
    metadata : Dict[str, Any]
        Arbitrary user and provenance metadata dictionary.
    """

    def __init__(
        self,
        z: Optional[torch.Tensor] = None,
        pos: Optional[torch.Tensor] = None,
        edge_index: Optional[torch.Tensor] = None,
        y: Optional[torch.Tensor] = None,
        x: Optional[torch.Tensor] = None,
        edge_attr: Optional[torch.Tensor] = None,
        weight: Optional[torch.Tensor] = None,
        forces: Optional[torch.Tensor] = None,
        dipole: Optional[torch.Tensor] = None,
        rotational_constants: Optional[torch.Tensor] = None,
        symbols: Optional[List[str]] = None,
        smiles: Optional[str] = None,
        conformer_id: Optional[int] = None,
        source_hash: Optional[str] = None,
        frequencies: Optional[torch.Tensor] = None,
        s2_spin: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        validate: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize ConformerData PyG tensor container with strict validation [M]/[D]."""
        super().__init__(
            x=x,
            edge_index=edge_index,
            edge_attr=edge_attr,
            y=y,
            pos=pos,
            z=z,
            **kwargs,
        )

        if z is not None:
            self.z = z
        if pos is not None:
            self.pos = pos
        if edge_index is not None:
            self.edge_index = edge_index
        elif not hasattr(self, "edge_index") or self.edge_index is None:
            self.edge_index = torch.empty((2, 0), dtype=torch.long, device=pos.device if pos is not None else None)

        if y is not None:
            self.y = y
        if x is not None:
            self.x = x
        if edge_attr is not None:
            self.edge_attr = edge_attr

        self.weight = (
            weight
            if weight is not None
            else torch.tensor([1.0], dtype=torch.float32, device=pos.device if pos is not None else None)
        )

        if forces is not None:
            self.forces = forces
        if dipole is not None:
            self.dipole = dipole
        if rotational_constants is not None:
            self.rotational_constants = rotational_constants

        if symbols is not None:
            self.symbols = list(symbols)
        elif z is not None:
            self.symbols = [ATOMIC_NUMBER_TO_SYMBOL.get(int(zi.item()), "X") for zi in z]
        else:
            self.symbols = []

        if smiles is not None:
            self.smiles = smiles
        if conformer_id is not None:
            self.conformer_id = conformer_id
        if source_hash is not None:
            self.source_hash = source_hash
        if frequencies is not None:
            self.frequencies = frequencies
        if s2_spin is not None:
            self.s2_spin = s2_spin

        self.metadata = dict(metadata) if metadata is not None else {}

        if validate and z is not None and pos is not None:
            validate_conformer_data(self)

    # --------------------------------------------------------------------------
    # Fallback Property Resolution for PyG GlobalStorage
    # --------------------------------------------------------------------------

    def __getattr__(self, key: str) -> Any:
        """Safe attribute access returning None for unassigned optional fields."""
        try:
            return super().__getattr__(key)
        except AttributeError:
            if key in (
                "forces",
                "dipole",
                "rotational_constants",
                "frequencies",
                "s2_spin",
                "conformer_id",
                "source_hash",
                "smiles",
                "y",
                "x",
                "edge_attr",
                "edge_index",
                "z",
                "pos",
                "symbols",
                "metadata",
                "weight",
            ):
                return None
            raise

    # --------------------------------------------------------------------------
    # PyG Batching Increment Override
    # --------------------------------------------------------------------------

    def __inc__(self, key: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        """Override PyG index incrementing during mini-batch concatenation.

        For `edge_index`, returns `self.z.size(0)` (the total number of node centers)
        so that edges across separate graphs in a batch are correctly offset.
        """
        if key == "edge_index":
            if self.z is not None:
                return self.z.size(0)
            if self.pos is not None:
                return self.pos.size(0)
            return self.num_nodes
        return super().__inc__(key, value, *args, **kwargs)

    # --------------------------------------------------------------------------
    # Pure Functional SE(3) Transformations (State Immutability Guaranteed)
    # --------------------------------------------------------------------------

    def translate(
        self, vector: Union[torch.Tensor, Sequence[float], np.ndarray]
    ) -> ConformerData:
        """Translate Cartesian coordinates immutably by translation vector T [D].

        Under spatial translation $\\mathbf{r}' = \\mathbf{r} + \\mathbf{T}$:
        - `pos` translates equivariantly.
        - `forces` are invariant (internal gradients remain identical).
        - `y`, `weight`, `rotational_constants` are invariant.
        - `dipole` is invariant for neutral molecules.

        Parameters
        ----------
        vector : Union[torch.Tensor, Sequence[float], np.ndarray]
            3D translation vector of shape (3,).

        Returns
        -------
        ConformerData
            A new ConformerData instance with translated coordinates.
        """
        if isinstance(vector, torch.Tensor):
            t_vec = vector.to(dtype=self.pos.dtype, device=self.pos.device)
        else:
            t_vec = torch.tensor(vector, dtype=self.pos.dtype, device=self.pos.device)

        if t_vec.shape != (3,) and t_vec.shape != (1, 3):
            raise ValueError(f"Translation vector must have shape (3,) or (1, 3), got {list(t_vec.shape)}")

        new_pos = self.pos + t_vec.squeeze()

        return ConformerData(
            z=self.z.clone() if self.z is not None else None,
            pos=new_pos,
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            dipole=self.dipole.clone() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols) if self.symbols is not None else None,
            smiles=self.smiles,
            conformer_id=self.conformer_id,
            source_hash=self.source_hash,
            frequencies=self.frequencies.clone() if self.frequencies is not None else None,
            s2_spin=self.s2_spin,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else {},
            validate=False,
        )

    def rotate(
        self, matrix: Union[torch.Tensor, Sequence[Sequence[float]], np.ndarray]
    ) -> ConformerData:
        """Rotate Cartesian coordinates, forces, and dipole immutably via SO(3) matrix R [D].

        Under 3D rotation $\\mathbf{r}' = \\mathbf{R} \\mathbf{r}$:
        - `pos` rotates equivariantly: $\\text{pos}' = \\text{pos} \\mathbf{R}^T$.
        - `forces` rotate equivariantly: $\\text{forces}' = \\text{forces} \\mathbf{R}^T$.
        - `dipole` rotates equivariantly: $\\boldsymbol{\\mu}' = \\boldsymbol{\\mu} \\mathbf{R}^T$.
        - `y`, `weight`, `rotational_constants` are scalar SO(3) invariants.

        Parameters
        ----------
        matrix : Union[torch.Tensor, Sequence[Sequence[float]], np.ndarray]
            3x3 orthogonal rotation matrix R.

        Returns
        -------
        ConformerData
            A new ConformerData instance with rotated geometric properties.
        """
        if isinstance(matrix, torch.Tensor):
            rot_mat = matrix.to(dtype=self.pos.dtype, device=self.pos.device)
        else:
            rot_mat = torch.tensor(matrix, dtype=self.pos.dtype, device=self.pos.device)

        if rot_mat.shape != (3, 3):
            raise ValueError(f"Rotation matrix must have shape (3, 3), got {list(rot_mat.shape)}")

        # Equivariant rotation: pos' = pos @ R^T
        new_pos = torch.matmul(self.pos, rot_mat.t())

        # Equivariant forces rotation if present
        new_forces = (
            torch.matmul(self.forces, rot_mat.t())
            if self.forces is not None
            else None
        )

        # Equivariant dipole rotation if present
        if self.dipole is not None:
            if self.dipole.dim() == 1:
                new_dipole = torch.matmul(rot_mat, self.dipole)
            else:
                new_dipole = torch.matmul(self.dipole, rot_mat.t())
        else:
            new_dipole = None

        return ConformerData(
            z=self.z.clone() if self.z is not None else None,
            pos=new_pos,
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=new_forces,
            dipole=new_dipole,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols) if self.symbols is not None else None,
            smiles=self.smiles,
            conformer_id=self.conformer_id,
            source_hash=self.source_hash,
            frequencies=self.frequencies.clone() if self.frequencies is not None else None,
            s2_spin=self.s2_spin,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else {},
            validate=False,
        )

    # --------------------------------------------------------------------------
    # Center of Mass and Spectroscopic Tensor Calculations
    # --------------------------------------------------------------------------

    def center_of_mass(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> torch.Tensor:
        """Compute Center of Mass (COM) coordinates in Angstroms [D].

        Dynamically queries standard atomic weights from the Mendeleev database
        if `masses` is omitted.

        $$\\mathbf{r}_{\\text{COM}} = \\frac{\\sum_{i=1}^N m_i \\mathbf{r}_i}{\\sum_{i=1}^N m_i}$$

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Optional explicit mass array of shape (N,).

        Returns
        -------
        torch.Tensor
            Center of mass vector of shape (3,) with dtype torch.float32.
        """
        if masses is not None:
            if isinstance(masses, torch.Tensor):
                m_tensor = masses.to(dtype=self.pos.dtype, device=self.pos.device)
            else:
                m_tensor = torch.tensor(masses, dtype=self.pos.dtype, device=self.pos.device)
        else:
            # Dynamic Mendeleev resolution (NEVER hardcoded)
            m_list = [get_atomic_mass(int(zi.item())) for zi in self.z]
            m_tensor = torch.tensor(m_list, dtype=self.pos.dtype, device=self.pos.device)

        if m_tensor.dim() == 1:
            m_tensor = m_tensor.unsqueeze(-1)

        total_mass = m_tensor.sum()
        if total_mass <= 0.0:
            raise ValueError(f"Total molecular mass must be positive, got {total_mass.item()}")

        com = (self.pos * m_tensor).sum(dim=0) / total_mass
        return com.squeeze()

    def center_at_com(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> ConformerData:
        """Return a new ConformerData centered at the molecular Center of Mass [D].

        State immutability: returns a fresh instance without mutating current coordinates.

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Optional explicit atomic mass vector.

        Returns
        -------
        ConformerData
            A new ConformerData instance centered at COM.
        """
        com = self.center_of_mass(masses=masses)
        return self.translate(-com)

    def compute_moment_of_inertia_tensor(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> torch.Tensor:
        """Construct the 3x3 Moment of Inertia tensor in the COM frame [D].

        $$I_{\\alpha \\beta} = \\sum_{i=1}^N m_i \\left( r_i'^2 \\delta_{\\alpha \\beta} - r'_{i,\\alpha} r'_{i,\\beta} \\right)$$

        where $\\mathbf{r}'_i = \\mathbf{r}_i - \\mathbf{r}_{\\text{COM}}$ in units of $u \\cdot \\text{\\AA}^2$.

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Atomic masses in Daltons. Queries Mendeleev dynamically if None.

        Returns
        -------
        torch.Tensor
            Moment of inertia tensor of shape (3, 3) with dtype torch.float32.
        """
        if masses is not None:
            if isinstance(masses, torch.Tensor):
                m = masses.to(dtype=self.pos.dtype, device=self.pos.device)
            else:
                m = torch.tensor(masses, dtype=self.pos.dtype, device=self.pos.device)
        else:
            m_list = [get_atomic_mass(int(zi.item())) for zi in self.z]
            m = torch.tensor(m_list, dtype=self.pos.dtype, device=self.pos.device)

        com = self.center_of_mass(masses=m)
        rel_pos = self.pos - com.unsqueeze(0)

        x = rel_pos[:, 0]
        y = rel_pos[:, 1]
        z = rel_pos[:, 2]

        ixx = (m * (y**2 + z**2)).sum()
        iyy = (m * (x**2 + z**2)).sum()
        izz = (m * (x**2 + y**2)).sum()

        ixy = -(m * x * y).sum()
        ixz = -(m * x * z).sum()
        iyz = -(m * y * z).sum()

        inertia = torch.tensor(
            [
                [ixx, ixy, ixz],
                [ixy, iyy, iyz],
                [ixz, iyz, izz],
            ],
            dtype=self.pos.dtype,
            device=self.pos.device,
        )
        return inertia

    def compute_principal_rotational_constants(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> torch.Tensor:
        """Compute principal spectroscopic rotational constants (A, B, C) in MHz [D].

        Rotational constant factor: $h / (8 \\pi^2) = 505379.008784\\text{ MHz} \\cdot u \\cdot \\text{\\AA}^2$.
        Eigenvalues sorted such that $I_a \\le I_b \\le I_c$, yielding $A \\ge B \\ge C$.

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Atomic masses in Daltons. Queries Mendeleev dynamically if None.

        Returns
        -------
        torch.Tensor
            Rotational constants tensor of shape (3,) in MHz: [A, B, C].
        """
        inertia = self.compute_moment_of_inertia_tensor(masses=masses)
        eigenvalues = torch.linalg.eigvalsh(inertia)
        eigenvalues, _ = torch.sort(eigenvalues)

        ia = float(eigenvalues[0].item())
        ib = float(eigenvalues[1].item())
        ic = float(eigenvalues[2].item())

        a_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ia) if ia > 1e-6 else 0.0
        b_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ib) if ib > 1e-6 else 0.0
        c_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ic) if ic > 1e-6 else 0.0

        return torch.tensor([a_const, b_const, c_const], dtype=torch.float32, device=self.pos.device)

    # --------------------------------------------------------------------------
    # Inter-Schema Conversions (MolecularData & ConformerRecord)
    # --------------------------------------------------------------------------

    @classmethod
    def from_molecular_data(cls, mol_data: MolecularData) -> ConformerData:
        """Construct a ConformerData instance from a MolecularData container [D].

        Parameters
        ----------
        mol_data : MolecularData
            Source MolecularData object.

        Returns
        -------
        ConformerData
            Converted ConformerData instance.
        """
        pos = mol_data.pos.to(dtype=torch.float32)
        z = mol_data.z.to(dtype=torch.long)
        edge_index = mol_data.edge_index.to(dtype=torch.long) if mol_data.edge_index is not None else None
        y = mol_data.y.to(dtype=torch.float32) if mol_data.y is not None else None
        x = mol_data.x.to(dtype=torch.float32) if mol_data.x is not None else None
        edge_attr = mol_data.edge_attr.to(dtype=torch.float32) if mol_data.edge_attr is not None else None
        weight = mol_data.weight.to(dtype=torch.float32) if mol_data.weight is not None else None
        forces = mol_data.forces.to(dtype=torch.float32) if mol_data.forces is not None else None
        dipole = mol_data.dipole.to(dtype=torch.float32) if mol_data.dipole is not None else None
        rotational_constants = (
            mol_data.rotational_constants.to(dtype=torch.float32)
            if mol_data.rotational_constants is not None
            else None
        )

        return cls(
            z=z,
            pos=pos,
            edge_index=edge_index,
            y=y,
            x=x,
            edge_attr=edge_attr,
            weight=weight,
            forces=forces,
            dipole=dipole,
            rotational_constants=rotational_constants,
            symbols=list(mol_data.symbols),
            metadata=dict(mol_data.metadata),
            validate=True,
        )

    def to_molecular_data(self) -> MolecularData:
        """Convert ConformerData instance back to a MolecularData container [D].

        Returns
        -------
        MolecularData
            Converted MolecularData object.
        """
        return MolecularData(
            z=self.z.clone(),
            pos=self.pos.clone(),
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            dipole=self.dipole.clone() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols) if self.symbols is not None else None,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else {},
        )

    @classmethod
    def from_conformer_record(
        cls,
        record: ConformerRecord,
        atomic_numbers: Sequence[int],
        smiles: Optional[str] = None,
        cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    ) -> ConformerData:
        """Construct a ConformerData instance from a ConformerRecord [D].

        Parameters
        ----------
        record : ConformerRecord
            Conformer record from raw parsing.
        atomic_numbers : Sequence[int]
            Atomic numbers Z corresponding to atom positions.
        smiles : Optional[str]
            Canonical SMILES string.
        cutoff : float
            Interatomic distance neighborhood graph cutoff in Angstroms.
        max_neighbors : int
            Maximum neighbor edges per atom.

        Returns
        -------
        ConformerData
            Constructed ConformerData instance.
        """
        pos = torch.tensor(record.coords, dtype=torch.float32)
        z = torch.tensor(atomic_numbers, dtype=torch.long)

        edge_index, _ = build_radius_graph(pos, cutoff=cutoff, max_neighbors=max_neighbors)

        y = torch.tensor([record.energy], dtype=torch.float32) if record.energy is not None else None
        weight = (
            torch.tensor([record.boltzmann_weight], dtype=torch.float32)
            if record.boltzmann_weight is not None
            else torch.tensor([1.0], dtype=torch.float32)
        )
        forces = torch.tensor(record.forces, dtype=torch.float32) if record.forces is not None else None
        dipole = torch.tensor(record.dipole, dtype=torch.float32) if record.dipole is not None else None
        rot_consts = (
            torch.tensor(record.rotational_constants, dtype=torch.float32)
            if record.rotational_constants is not None
            else None
        )
        freqs = (
            torch.tensor(record.frequencies, dtype=torch.float32)
            if record.frequencies is not None
            else None
        )

        metadata = dict(record.metadata)
        metadata["relative_energy"] = record.relative_energy
        if record.qm_method:
            metadata["qm_method"] = record.qm_method

        return cls(
            z=z,
            pos=pos,
            edge_index=edge_index,
            y=y,
            weight=weight,
            forces=forces,
            dipole=dipole,
            rotational_constants=rot_consts,
            smiles=smiles,
            conformer_id=record.conformer_id,
            source_hash=record.source_hash,
            frequencies=freqs,
            s2_spin=record.s2_spin,
            metadata=metadata,
            validate=True,
        )

    def to_conformer_record(self, conformer_id: Optional[int] = None) -> ConformerRecord:
        """Convert ConformerData back to an immutable ConformerRecord [D].

        Parameters
        ----------
        conformer_id : Optional[int]
            Optional override for sequential conformer integer ID.

        Returns
        -------
        ConformerRecord
            Converted conformer record.
        """
        coords = self.pos.detach().cpu().numpy().astype(np.float64)
        y_tensor = getattr(self, "y", None)
        energy = float(y_tensor.item()) if y_tensor is not None and y_tensor.numel() > 0 else 0.0
        meta = self.metadata if getattr(self, "metadata", None) is not None else {}
        relative_energy = float(meta.get("relative_energy", 0.0))
        w_tensor = getattr(self, "weight", None)
        boltzmann_weight = float(w_tensor.item()) if w_tensor is not None and w_tensor.numel() > 0 else 1.0

        f_tensor = getattr(self, "forces", None)
        forces = f_tensor.detach().cpu().numpy().astype(np.float64) if f_tensor is not None else None
        d_tensor = getattr(self, "dipole", None)
        dipole = d_tensor.detach().cpu().numpy().astype(np.float64) if d_tensor is not None else None
        rc_tensor = getattr(self, "rotational_constants", None)
        rot_consts = (
            rc_tensor.detach().cpu().numpy().astype(np.float64)
            if rc_tensor is not None
            else None
        )
        freq_tensor = getattr(self, "frequencies", None)
        freqs = (
            freq_tensor.detach().cpu().numpy().astype(np.float64)
            if freq_tensor is not None
            else None
        )
        cid_val = getattr(self, "conformer_id", None)
        cid = conformer_id if conformer_id is not None else (cid_val if cid_val is not None else 0)

        return ConformerRecord(
            conformer_id=cid,
            coords=coords,
            energy=energy,
            relative_energy=relative_energy,
            boltzmann_weight=boltzmann_weight,
            forces=forces,
            dipole=dipole,
            rotational_constants=rot_consts,
            qm_method=meta.get("qm_method", None),
            source_hash=getattr(self, "source_hash", None),
            s2_spin=getattr(self, "s2_spin", None),
            frequencies=freqs,
            metadata=copy.deepcopy(meta),
        )

    @classmethod
    def from_xyz_file(
        cls,
        file_path: Union[str, Path],
        energy: Optional[float] = None,
        cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    ) -> ConformerData:
        """Parse an authentic Cartesian .xyz file into a validated ConformerData instance [M].

        Parameters
        ----------
        file_path : Union[str, Path]
            Path to the .xyz file.
        energy : Optional[float]
            Optional total energy in eV.
        cutoff : float
            Radial graph neighbor cutoff in Angstroms.
        max_neighbors : int
            Maximum incoming neighbors per atom.

        Returns
        -------
        ConformerData
            Validated ConformerData instance with SHA-256 provenance hash.
        """
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"XYZ file not found: {path}")

        sha256_hash = compute_file_sha256(path)

        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if len(lines) < 3:
            raise ValueError(f"XYZ file {path} has fewer than 3 non-empty lines.")

        num_atoms = int(lines[0])
        comment = lines[1]

        symbols: List[str] = []
        atomic_numbers: List[int] = []
        coords: List[List[float]] = []

        for line_idx, line in enumerate(lines[2 : 2 + num_atoms]):
            tokens = line.split()
            if len(tokens) < 4:
                raise ValueError(f"Malformed coordinate line {line_idx + 3} in XYZ file: '{line}'")
            sym = tokens[0].capitalize()
            if sym not in SYMBOL_TO_ATOMIC_NUMBER:
                raise ValueError(f"Unrecognized chemical symbol '{sym}' on line {line_idx + 3}")
            z_val = SYMBOL_TO_ATOMIC_NUMBER[sym]
            x_val, y_val, z_pos = float(tokens[1]), float(tokens[2]), float(tokens[3])

            symbols.append(sym)
            atomic_numbers.append(z_val)
            coords.append([x_val, y_val, z_pos])

        pos_tensor = torch.tensor(coords, dtype=torch.float32)
        z_tensor = torch.tensor(atomic_numbers, dtype=torch.long)

        edge_index, _ = build_radius_graph(pos_tensor, cutoff=cutoff, max_neighbors=max_neighbors)

        y_tensor = torch.tensor([energy], dtype=torch.float32) if energy is not None else None

        metadata = {"xyz_comment": comment, "source_file": str(path)}

        return cls(
            z=z_tensor,
            pos=pos_tensor,
            edge_index=edge_index,
            y=y_tensor,
            symbols=symbols,
            source_hash=sha256_hash,
            metadata=metadata,
            validate=True,
        )


# ==============================================================================
# 3. Pure Functional Schema Utilities
# ==============================================================================


def rotate_conformer_data(
    data: ConformerData,
    matrix: Union[torch.Tensor, Sequence[Sequence[float]], np.ndarray],
) -> ConformerData:
    """Pure functional wrapper for ConformerData rotation [D]."""
    return data.rotate(matrix)


def translate_conformer_data(
    data: ConformerData,
    vector: Union[torch.Tensor, Sequence[float], np.ndarray],
) -> ConformerData:
    """Pure functional wrapper for ConformerData translation [D]."""
    return data.translate(vector)


def center_at_com_conformer_data(
    data: ConformerData,
    masses: Optional[Union[torch.Tensor, Sequence[float]]] = None,
) -> ConformerData:
    """Pure functional wrapper for ConformerData center-of-mass centering [D]."""
    return data.center_at_com(masses=masses)


def batch_conformer_data(data_list: Sequence[ConformerData]) -> Batch:
    """Collate a sequence of ConformerData objects into a unified PyG Batch [D].

    Parameters
    ----------
    data_list : Sequence[ConformerData]
        List or sequence of ConformerData instances.

    Returns
    -------
    torch_geometric.data.Batch
        Unified batched graph container.
    """
    return Batch.from_data_list(list(data_list))
