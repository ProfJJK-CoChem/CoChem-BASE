"""CoChem-GEOM: PyTorch Lightning Execution Orchestrator and Physics-Informed Loss Layer.
=====================================================================================
Establishes the Tier 3 execution and orchestration layer bridging Tier 1 (Data Ingestion)
and Tier 2 (Representation & Physics-Informed ML Models). Manages the training loop,
gradient clipping, learning rate scheduling (OneCycleLR / Cosine Annealing with Warmup),
mixed-precision (AMP bf16-mixed), Distributed Data Parallel (DDP) scaling, and analytical
force autograd management during validation and testing cycles.

Authoritative Standards & Directives:
- Method Matrix v4.1: Physics-Informed Joint Energy-Force Learning & Boltzmann Weighting
- SWEBOK v3 / ISO 25010 Software Engineering & Quality Standards
- Mendeleev Library Mandate: All atomic/isotopic masses dynamically resolved via `mendeleev`
- SE(3) Equivariance & Invariance: Strict separation of spatial pos [N, 3] from invariant features
- State Immutability: Pure functional geometric transformations (`data.pos = data.pos + update`)
- Validation Autograd Override: Explicit `torch.set_grad_enabled(True)` for force evaluations
- Dynamic Path Resolution: Cross-platform dynamic pathing via `pathlib` and environment variables
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Mandate: 100% authentic physical tensor mathematics and real execution
"""

from __future__ import annotations

import dataclasses
import logging
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, Union

import mendeleev
import numpy as np
import pytorch_lightning as pl
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR

logger = logging.getLogger("cochem_geom.training.lightning_module")


# ==============================================================================
# 1. Fundamental Physical Constants & Provenance Declarations (CODATA 2018/2022)
# ==============================================================================

SPEED_OF_LIGHT_M_S: float = 299792458.0
"""Speed of light in vacuum in meters per second (exact) [M]."""

PLANCK_CONSTANT_J_S: float = 6.62607015e-34
"""Planck constant in Joule seconds (exact) [M]."""

BOLTZMANN_CONSTANT_J_K: float = 1.380649e-23
"""Boltzmann constant in Joules per Kelvin (exact) [M]."""

BOLTZMANN_CONSTANT_EV_K: float = 8.617333262145e-5
"""Boltzmann constant in electron-volts per Kelvin [D]."""

ELEMENTARY_CHARGE_C: float = 1.602176634e-19
"""Elementary charge in Coulombs (exact) [M]."""

AVOGADRO_CONSTANT_MOL: float = 6.02214076e23
"""Avogadro constant per mole (exact) [M]."""

ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27
"""Unified atomic mass unit / Dalton in kilograms [M]."""

BOHR_RADIUS_ANGSTROM: float = 0.529177210903
"""Bohr radius in Angstroms [M]."""

HARTREE_TO_EV: float = 27.211386245988
"""Conversion factor from Hartree to electron-volts [D]."""

EV_TO_HARTREE: float = 1.0 / HARTREE_TO_EV
"""Conversion factor from electron-volts to Hartree [D]."""

STANDARD_TEMPERATURE_K: float = 298.15
"""Standard ambient reference temperature in Kelvin (25 deg C) [M]."""

DEFAULT_GRADIENT_CLIP_VAL: float = 1.0
"""Default gradient clipping threshold to prevent NaN collapse in spatial GNNs [E]."""

DEFAULT_WARMUP_PCT: float = 0.1
"""Default fraction of training steps allocated to linear learning rate warmup (10%) [E]."""

DEFAULT_LR: float = 1e-4
"""Default base learning rate for AdamW optimization [E]."""

DEFAULT_WEIGHT_DECAY: float = 1e-5
"""Default L2 regularization weight decay for 2D+ parameter tensors [E]."""

DEFAULT_ENERGY_WEIGHT: float = 1.0
"""Default scalar energy loss scaling factor lambda_energy [E]."""

DEFAULT_FORCE_WEIGHT: float = 0.0
"""Default vector force loss scaling factor lambda_force (0.0 = energy only) [E]."""

DEFAULT_MAX_EPOCHS: int = 100
"""Default maximum training epochs [E]."""

DEFAULT_STEPS_PER_EPOCH: int = 1000
"""Default estimation of gradient update steps per epoch [E]."""

DEFAULT_MAX_Z: int = 100
"""Maximum supported atomic number Z for embedding tables (1-100) [M]."""

DEFAULT_RBF_CUTOFF: float = 5.0
"""Default radial basis cutoff distance in Angstroms [E]."""


# ==============================================================================
# 2. Dynamic Mendeleev Library Mass Resolution Mandate
# ==============================================================================

def get_element_mass(element_identifier: Union[str, int]) -> float:
    """Dynamically query standard atomic weight from mendeleev library [M].

    Hardcoded atomic weight lookup tables are strictly forbidden by architectural mandate.

    Parameters
    ----------
    element_identifier : Union[str, int]
        Chemical element symbol (e.g., 'C', 'O') or atomic number Z (e.g., 6, 8).

    Returns
    -------
    float
        Standard atomic mass in Daltons (atomic mass units).
    """
    elem = mendeleev.element(element_identifier)
    weight = elem.atomic_weight
    if weight is not None:
        return float(weight)
    if elem.isotopes:
        most_abundant = max(
            elem.isotopes,
            key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
        )
        if most_abundant.mass is not None:
            return float(most_abundant.mass)
    if elem.mass is not None:
        return float(elem.mass)
    raise ValueError(f"Standard atomic mass not found for element '{element_identifier}'")


def get_atomic_masses(atomic_numbers: torch.Tensor) -> torch.Tensor:
    """Dynamically query atomic masses for a 1D tensor of atomic numbers [M].

    Parameters
    ----------
    atomic_numbers : torch.Tensor
        1D tensor of integer atomic numbers Z [N].

    Returns
    -------
    torch.Tensor
        1D tensor of atomic masses in Daltons [N] (float32).
    """
    masses: List[float] = []
    for z_val in atomic_numbers.view(-1).tolist():
        masses.append(get_element_mass(int(z_val)))
    return torch.tensor(masses, dtype=torch.float32, device=atomic_numbers.device)


# ==============================================================================
# 3. State Immutability & SE(3) Pure Geometric Operations
# ==============================================================================

def translate_coordinates(pos: torch.Tensor, shift: torch.Tensor) -> torch.Tensor:
    """Pure functional translation preserving state immutability [D].

    Enforces `pos_new = pos + shift` (never in-place mutation `pos += shift`).

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinate tensor [N, 3].
    shift : torch.Tensor
        Translation vector [3] or [1, 3].

    Returns
    -------
    torch.Tensor
        New translated coordinate tensor [N, 3].
    """
    return pos + shift.view(1, 3)


def rotate_coordinates(pos: torch.Tensor, rotation_matrix: torch.Tensor) -> torch.Tensor:
    """Pure functional 3D rotation applying an SO(3) orthogonal matrix [D].

    `pos_new = pos @ R.T`

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinate tensor [N, 3].
    rotation_matrix : torch.Tensor
        Orthogonal SO(3) 3x3 rotation matrix.

    Returns
    -------
    torch.Tensor
        New rotated coordinate tensor [N, 3].
    """
    return torch.matmul(pos, rotation_matrix.T)


def center_coordinates(pos: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """Pure functional coordinate centering subtracting the geometric centroid [D].

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinate tensor [N, 3].

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        Centered coordinates [N, 3] and the computed centroid [3].
    """
    center = pos.mean(dim=0, keepdim=True)
    return pos - center, center.squeeze(0)


def apply_coordinate_delta(pos: torch.Tensor, delta: torch.Tensor) -> torch.Tensor:
    """Immutable coordinate update rule: `pos_new = pos + delta` [D].

    Parameters
    ----------
    pos : torch.Tensor
        Current coordinate tensor [N, 3].
    delta : torch.Tensor
        Displacement delta tensor [N, 3].

    Returns
    -------
    torch.Tensor
        Updated coordinate tensor [N, 3].
    """
    return pos + delta


# ==============================================================================
# 4. Data Schemas & Conformer Batch Structures
# ==============================================================================

@dataclasses.dataclass
class ConformerData:
    """Individual molecular conformer representation.

    Strictly separates Cartesian coordinates from non-spatial node features.
    """
    pos: torch.Tensor
    """Cartesian coordinates [N, 3] in float32."""
    z: torch.Tensor
    """Atomic numbers [N] in int64."""
    y: torch.Tensor
    """Ground-truth scalar energy [1, 1] or [1] in float32."""
    x: Optional[torch.Tensor] = None
    """Non-spatial node features [N, F]."""
    force: Optional[torch.Tensor] = None
    """Interatomic forces [N, 3] in float32."""
    weight: Optional[torch.Tensor] = None
    """Thermodynamic Boltzmann weight [1, 1] or [1]."""
    batch: Optional[torch.Tensor] = None
    """Graph membership index vector [N]."""
    edge_index: Optional[torch.Tensor] = None
    """Pairwise edge indices [2, E] in int64."""
    num_graphs: int = 1
    """Number of graphs represented."""

    def to(self, device: Union[torch.device, str]) -> ConformerData:
        """Move all contained tensors to target device."""
        target_dev = torch.device(device) if isinstance(device, str) else device
        return ConformerData(
            pos=self.pos.to(target_dev),
            z=self.z.to(target_dev),
            y=self.y.to(target_dev),
            x=self.x.to(target_dev) if self.x is not None else None,
            force=self.force.to(target_dev) if self.force is not None else None,
            weight=self.weight.to(target_dev) if self.weight is not None else None,
            batch=self.batch.to(target_dev) if self.batch is not None else None,
            edge_index=self.edge_index.to(target_dev) if self.edge_index is not None else None,
            num_graphs=self.num_graphs,
        )


@dataclasses.dataclass
class ConformerBatch:
    """Batched molecular conformer graph collection for PyG / PyTorch execution."""
    pos: torch.Tensor
    """Concatenated Cartesian coordinates [Total_N, 3]."""
    z: torch.Tensor
    """Concatenated atomic numbers [Total_N]."""
    y: torch.Tensor
    """Batched energies [Batch_Size, 1]."""
    batch: torch.Tensor
    """Graph membership index vector [Total_N]."""
    x: Optional[torch.Tensor] = None
    """Batched node features [Total_N, F]."""
    force: Optional[torch.Tensor] = None
    """Batched interatomic forces [Total_N, 3]."""
    weight: Optional[torch.Tensor] = None
    """Batched Boltzmann weights [Batch_Size, 1]."""
    edge_index: Optional[torch.Tensor] = None
    """Batched edge indices [2, Total_E]."""
    num_graphs: int = 1
    """Batch size (number of graphs)."""

    def to(self, device: Union[torch.device, str]) -> ConformerBatch:
        """Move all contained tensors to target device."""
        target_dev = torch.device(device) if isinstance(device, str) else device
        return ConformerBatch(
            pos=self.pos.to(target_dev),
            z=self.z.to(target_dev),
            y=self.y.to(target_dev),
            batch=self.batch.to(target_dev),
            x=self.x.to(target_dev) if self.x is not None else None,
            force=self.force.to(target_dev) if self.force is not None else None,
            weight=self.weight.to(target_dev) if self.weight is not None else None,
            edge_index=self.edge_index.to(target_dev) if self.edge_index is not None else None,
            num_graphs=self.num_graphs,
        )


def collate_conformers(conformers: Sequence[ConformerData]) -> ConformerBatch:
    """Collate a sequence of ConformerData objects into a single contiguous ConformerBatch.

    Parameters
    ----------
    conformers : Sequence[ConformerData]
        List or sequence of individual ConformerData graphs.

    Returns
    -------
    ConformerBatch
        Batched tensor structure with proper node-graph indexing.
    """
    pos_list: List[torch.Tensor] = []
    z_list: List[torch.Tensor] = []
    y_list: List[torch.Tensor] = []
    batch_list: List[torch.Tensor] = []
    x_list: List[torch.Tensor] = []
    force_list: List[torch.Tensor] = []
    weight_list: List[torch.Tensor] = []
    edge_index_list: List[torch.Tensor] = []

    has_x = any(s.x is not None for s in conformers)
    has_force = any(s.force is not None for s in conformers)
    has_edges = any(s.edge_index is not None for s in conformers)

    node_offset = 0
    for i, item in enumerate(conformers):
        n_atoms = item.pos.shape[0]
        pos_list.append(item.pos.to(torch.float32))
        z_list.append(item.z.to(torch.long))
        y_list.append(item.y.view(1, -1).to(torch.float32))
        batch_list.append(torch.full((n_atoms,), i, dtype=torch.long, device=item.pos.device))

        if has_x:
            if item.x is not None:
                x_list.append(item.x.to(torch.float32))
            else:
                x_list.append(torch.zeros((n_atoms, 1), dtype=torch.float32, device=item.pos.device))

        if has_force:
            if item.force is not None:
                force_list.append(item.force.to(torch.float32))
            else:
                force_list.append(torch.zeros((n_atoms, 3), dtype=torch.float32, device=item.pos.device))

        if item.weight is not None:
            weight_list.append(item.weight.view(1, 1).to(torch.float32))
        else:
            weight_list.append(torch.ones((1, 1), dtype=torch.float32, device=item.y.device))

        if has_edges:
            if item.edge_index is not None:
                shifted_edges = item.edge_index + node_offset
                edge_index_list.append(shifted_edges.to(torch.long))
        node_offset += n_atoms

    batched_pos = torch.cat(pos_list, dim=0)
    batched_z = torch.cat(z_list, dim=0)
    batched_y = torch.cat(y_list, dim=0)
    batched_batch = torch.cat(batch_list, dim=0)
    batched_x = torch.cat(x_list, dim=0) if has_x else None
    batched_force = torch.cat(force_list, dim=0) if has_force else None
    batched_weight = torch.cat(weight_list, dim=0)
    batched_edge_index = torch.cat(edge_index_list, dim=1) if has_edges and edge_index_list else None

    return ConformerBatch(
        pos=batched_pos,
        z=batched_z,
        y=batched_y,
        batch=batched_batch,
        x=batched_x,
        force=batched_force,
        weight=batched_weight,
        edge_index=batched_edge_index,
        num_graphs=len(conformers),
    )


# ==============================================================================
# 5. Physics-Informed Joint Loss Layer
# ==============================================================================

class PhysicsInformedLoss(nn.Module):
    """Joint loss function optimizing scalar energies and analytical vector forces.

    Incorporates thermodynamic Boltzmann probabilities (data.weight) to correctly
    weight low-energy minima while mitigating extensive vs intensive scaling biases.
    """
    def __init__(self, energy_weight: float = DEFAULT_ENERGY_WEIGHT, force_weight: float = DEFAULT_FORCE_WEIGHT):
        super().__init__()
        self.energy_weight = float(energy_weight)  # [E]
        self.force_weight = float(force_weight)    # [E]
        self.mse_loss = nn.MSELoss(reduction="none")

    def forward(
        self,
        preds: Dict[str, torch.Tensor],
        data: Any,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """Compute Boltzmann-weighted joint loss conforming to SRS Document 7.

        Parameters
        ----------
        preds : Dict[str, torch.Tensor]
            Dictionary containing predicted "energy" [B, 1] and optionally "forces" [N, 3].
        data : Any
            ConformerData, ConformerBatch, or PyG Data/Batch containing ground truth targets.

        Returns
        -------
        Tuple[torch.Tensor, Dict[str, torch.Tensor]]
            Tuple of (total_scalar_loss, metrics_dictionary).
        """
        device = data.y.device if hasattr(data, "y") and isinstance(data.y, torch.Tensor) else preds["energy"].device
        total_loss = torch.tensor(0.0, device=device, dtype=torch.float32)
        metrics: Dict[str, torch.Tensor] = {}

        # 1. Boltzmann-Weighted Energy Loss (Graph-Level)
        e_pred = preds["energy"].view(-1)
        e_target = data.y.view(-1) if hasattr(data, "y") else torch.zeros_like(e_pred)

        weights = getattr(data, "weight", None)
        if weights is not None and isinstance(weights, torch.Tensor):
            weights = weights.view(-1).to(device)
            if weights.numel() != e_target.numel():
                if weights.numel() == 1:
                    weights = weights.expand_as(e_target)
                else:
                    weights = torch.ones_like(e_target)
        else:
            weights = torch.ones_like(e_target)

        # Unweighted MSE Shape: [Batch_Size]
        e_loss_unweighted = self.mse_loss(e_pred, e_target)

        # Apply thermodynamic probabilities and average over the batch
        e_loss = (e_loss_unweighted * weights).mean()

        metrics["loss_energy"] = e_loss.detach()
        total_loss = total_loss + self.energy_weight * e_loss

        # 2. Boltzmann-Weighted Force Loss (Node-Level, if applicable)
        if self.force_weight > 0.0 and "forces" in preds and getattr(data, "force", None) is not None:
            f_pred = preds["forces"]
            f_target = data.force

            if f_target is not None:
                # MSE Shape: [N_atoms, 3] -> Mean over Cartesian axes -> [N_atoms]
                f_loss_unweighted = self.mse_loss(f_pred, f_target).mean(dim=-1)

                # Expand graph-level weights to node-level using the PyG batch index vector
                batch_idx = getattr(data, "batch", None)
                if batch_idx is not None and isinstance(batch_idx, torch.Tensor):
                    batch_idx = batch_idx.view(-1).to(device)
                    node_weights = weights[batch_idx]
                else:
                    node_weights = weights[0].expand(f_pred.size(0)) if weights.numel() > 0 else torch.ones(f_pred.size(0), device=device)

                # Scale node errors by their parent graph's thermodynamic weight
                f_loss = (f_loss_unweighted * node_weights).mean()

                metrics["loss_force"] = f_loss.detach()
                total_loss = total_loss + self.force_weight * f_loss

        metrics["loss"] = total_loss.detach()
        return total_loss, metrics


# ==============================================================================
# 6. Dynamic Model Registry & Neural Network Backbones (Zero-Mock)
# ==============================================================================

class ModelRegistry:
    """Centralized registry for dynamically instantiating 3D GNN architectures.

    Enables strict dependency injection via configuration schemas.
    """
    _registry: Dict[str, Type[nn.Module]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[Type[nn.Module]], Type[nn.Module]]:
        """Decorator to register a GNN class under a string alias."""
        def inner_wrapper(model_cls: Type[nn.Module]) -> Type[nn.Module]:
            if not issubclass(model_cls, nn.Module):
                raise TypeError(f"{model_cls.__name__} must inherit from torch.nn.Module")
            alias = str(name).lower()
            if alias in cls._registry:
                logger.warning("Overwriting existing registry entry for model '%s'", alias)
            cls._registry[alias] = model_cls
            return model_cls
        return inner_wrapper

    @classmethod
    def build(cls, name: str, **kwargs: Any) -> nn.Module:
        """Instantiate a model by its registered string alias with kwargs."""
        alias = str(name).lower()
        if alias not in cls._registry:
            raise KeyError(f"Model '{alias}' not found in registry. Available models: {list(cls._registry.keys())}")
        model_cls = cls._registry[alias]
        return model_cls(**kwargs)

    @classmethod
    def list_models(cls) -> List[str]:
        """Return list of all registered model aliases."""
        return list(cls._registry.keys())


class RadialBasisExpansion(nn.Module):
    """Gaussian Radial Basis Function (RBF) expansion of pairwise interatomic distances."""
    def __init__(self, num_radial: int = 32, cutoff: float = DEFAULT_RBF_CUTOFF):
        super().__init__()
        self.num_radial = int(num_radial)
        self.cutoff = float(cutoff)

        centers = torch.linspace(0.0, cutoff, num_radial, dtype=torch.float32)
        self.register_buffer("centers", centers)
        gamma = float(num_radial / cutoff)
        self.register_buffer("gamma", torch.tensor(gamma, dtype=torch.float32))

    def forward(self, distances: torch.Tensor) -> torch.Tensor:
        """Expand pairwise distances into Gaussian RBF features with smooth cosine cutoff."""
        dist_expanded = distances.unsqueeze(-1)
        rbf = torch.exp(-self.gamma * (dist_expanded - self.centers) ** 2)
        cutoff_factor = 0.5 * (torch.cos(torch.clamp(distances / self.cutoff, max=1.0) * math.pi) + 1.0)
        return rbf * cutoff_factor.unsqueeze(-1)


class SchNetInteractionBlock(nn.Module):
    """Continuous-filter convolutional interaction block for SchNet message passing."""
    def __init__(self, hidden_channels: int, num_radial: int):
        super().__init__()
        self.filter_network = nn.Sequential(
            nn.Linear(num_radial, hidden_channels),
            nn.SiLU(),
            nn.Linear(hidden_channels, hidden_channels),
        )
        self.atom_linear = nn.Linear(hidden_channels, hidden_channels)
        self.output_linear = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels),
            nn.SiLU(),
            nn.Linear(hidden_channels, hidden_channels),
        )

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor, edge_rbf: torch.Tensor) -> torch.Tensor:
        """Perform continuous-filter convolution message passing."""
        if edge_index.size(1) == 0:
            return h

        src, dst = edge_index[0], edge_index[1]
        w = self.filter_network(edge_rbf)
        h_src = self.atom_linear(h)[src]
        messages = h_src * w

        agg = torch.zeros_like(h)
        agg.index_add_(0, dst, messages)

        update = self.output_linear(agg)
        return h + update  # Pure immutable addition


@ModelRegistry.register("schnet")
class SchNetModel(nn.Module):
    """Standard SchNet architecture for 3D molecular energy and analytical force prediction."""
    def __init__(
        self,
        hidden_channels: int = 128,
        num_layers: int = 6,
        num_radial: int = 32,
        cutoff: float = DEFAULT_RBF_CUTOFF,
        max_z: int = DEFAULT_MAX_Z,
    ):
        super().__init__()
        self.hidden_channels = int(hidden_channels)
        self.num_layers = int(num_layers)
        self.cutoff = float(cutoff)
        self.max_z = int(max_z)

        self.embedding = nn.Embedding(max_z + 1, hidden_channels)
        self.rbf = RadialBasisExpansion(num_radial=num_radial, cutoff=cutoff)
        self.interactions = nn.ModuleList([
            SchNetInteractionBlock(hidden_channels, num_radial)
            for _ in range(num_layers)
        ])
        self.readout = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels // 2),
            nn.SiLU(),
            nn.Linear(hidden_channels // 2, 1),
        )

    def _build_edges(self, pos: torch.Tensor, batch: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Construct radius graph pairwise edges strictly within each molecule in the batch."""
        diff = pos.unsqueeze(1) - pos.unsqueeze(0)  # [N, N, 3]
        dist = torch.norm(diff, p=2, dim=-1)        # [N, N]

        same_molecule = batch.unsqueeze(1) == batch.unsqueeze(0)
        mask = (dist < self.cutoff) & (dist > 1e-6) & same_molecule

        edge_index = mask.nonzero(as_tuple=False).t()  # [2, E]
        edge_dist = dist[mask]
        return edge_index, edge_dist

    def forward(self, data: Any) -> Dict[str, torch.Tensor]:
        """Forward pass predicting total molecular scalar energy."""
        pos = data.pos
        z = data.z
        batch = getattr(data, "batch", None)
        if batch is None:
            batch = torch.zeros(pos.size(0), dtype=torch.long, device=pos.device)

        edge_index, edge_dist = self._build_edges(pos, batch)

        h = self.embedding(z)
        if edge_index.size(1) > 0:
            edge_rbf = self.rbf(edge_dist)
            for interaction in self.interactions:
                h = interaction(h, edge_index, edge_rbf)

        atomic_energies = self.readout(h)  # [N, 1]

        num_graphs = int(batch.max().item() + 1) if batch.numel() > 0 else 1
        total_energy = torch.zeros((num_graphs, 1), dtype=torch.float32, device=pos.device)
        total_energy.index_add_(0, batch, atomic_energies)

        return {"energy": total_energy}

    def compute_forces(self, data: Any) -> Dict[str, torch.Tensor]:
        """Derive interatomic forces analytically as negative gradient: F = - dE / dr."""
        pos = data.pos
        orig_requires_grad = pos.requires_grad

        batch = getattr(data, "batch", None)
        if batch is None:
            batch = torch.zeros(pos.size(0), dtype=torch.long, device=pos.device)

        with torch.inference_mode(False), torch.enable_grad():
            pos_eval = pos.clone().detach().requires_grad_(True) if not orig_requires_grad else pos
            temp_data = ConformerData(
                pos=pos_eval,
                z=data.z,
                y=getattr(data, "y", torch.zeros((1, 1), device=pos.device)),
                weight=getattr(data, "weight", None),
                batch=batch,
            )
            preds = self.forward(temp_data)
            energy = preds["energy"]
            if not energy.requires_grad:
                forces = torch.zeros_like(pos_eval)
            else:
                grad_tuple = torch.autograd.grad(
                    outputs=energy.sum(),
                    inputs=pos_eval,
                    create_graph=self.training,
                    retain_graph=self.training,
                    allow_unused=True,
                )
                forces = -grad_tuple[0] if grad_tuple[0] is not None else torch.zeros_like(pos_eval)

        return {"energy": energy, "forces": forces}


class EGNNLayer(nn.Module):
    """Equivariant Graph Neural Network (EGNN) coordinate and feature updating block.

    Guarantees state immutability and exact SE(3) / E(n) equivariance.
    """
    def __init__(self, hidden_channels: int, edge_feat_dim: int = 0):
        super().__init__()
        self.message_mlp = nn.Sequential(
            nn.Linear(hidden_channels * 2 + 1 + edge_feat_dim, hidden_channels),
            nn.SiLU(),
            nn.Linear(hidden_channels, hidden_channels),
            nn.SiLU(),
        )
        self.coord_mlp = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels),
            nn.SiLU(),
            nn.Linear(hidden_channels, 1, bias=False),
        )
        self.node_mlp = nn.Sequential(
            nn.Linear(hidden_channels * 2, hidden_channels),
            nn.SiLU(),
            nn.Linear(hidden_channels, hidden_channels),
        )

    def forward(
        self,
        h: torch.Tensor,
        pos: torch.Tensor,
        edge_index: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Equivariant coordinate and invariant feature message passing."""
        if edge_index.size(1) == 0:
            return h, pos

        src, dst = edge_index[0], edge_index[1]
        diff = pos[src] - pos[dst]  # [E, 3]
        dist_sq = (diff ** 2).sum(dim=-1, keepdim=True)  # [E, 1]

        msg_input = torch.cat([h[src], h[dst], dist_sq], dim=-1)
        msg = self.message_mlp(msg_input)  # [E, hidden]

        # Equivariant Coordinate Update
        coord_weights = self.coord_mlp(msg)  # [E, 1]
        coord_messages = diff * coord_weights  # [E, 3]
        coord_agg = torch.zeros_like(pos)
        coord_agg.index_add_(0, dst, coord_messages)
        pos_new = pos + coord_agg  # Pure immutable update [E]

        # Invariant Node Feature Update
        node_agg = torch.zeros_like(h)
        node_agg.index_add_(0, dst, msg)
        h_new = h + self.node_mlp(torch.cat([h, node_agg], dim=-1))

        return h_new, pos_new


@ModelRegistry.register("egnn")
class EquivariantGNNModel(nn.Module):
    """Equivariant Graph Neural Network (EGNN) predicting scalar energies and analytical forces."""
    def __init__(
        self,
        hidden_channels: int = 128,
        num_layers: int = 6,
        cutoff: float = 10.0,
        max_z: int = DEFAULT_MAX_Z,
    ):
        super().__init__()
        self.cutoff = float(cutoff)
        self.embedding = nn.Embedding(max_z + 1, hidden_channels)
        self.layers = nn.ModuleList([
            EGNNLayer(hidden_channels)
            for _ in range(num_layers)
        ])
        self.readout = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels // 2),
            nn.SiLU(),
            nn.Linear(hidden_channels // 2, 1),
        )

    def _build_edges(self, pos: torch.Tensor, batch: torch.Tensor) -> torch.Tensor:
        """Build radius graph edge index."""
        diff = pos.unsqueeze(1) - pos.unsqueeze(0)
        dist = torch.norm(diff, p=2, dim=-1)
        same_mol = batch.unsqueeze(1) == batch.unsqueeze(0)
        mask = (dist < self.cutoff) & (dist > 1e-6) & same_mol
        return mask.nonzero(as_tuple=False).t()

    def forward(self, data: Any) -> Dict[str, torch.Tensor]:
        """Compute total energy from invariant node embeddings after equivariant message passing."""
        pos = data.pos
        z = data.z
        batch = getattr(data, "batch", None)
        if batch is None:
            batch = torch.zeros(pos.size(0), dtype=torch.long, device=pos.device)

        edge_index = self._build_edges(pos, batch)
        h = self.embedding(z)

        for layer in self.layers:
            h, pos = layer(h, pos, edge_index)

        atomic_energies = self.readout(h)
        num_graphs = int(batch.max().item() + 1) if batch.numel() > 0 else 1
        total_energy = torch.zeros((num_graphs, 1), dtype=torch.float32, device=pos.device)
        total_energy.index_add_(0, batch, atomic_energies)

        return {"energy": total_energy}

    def compute_forces(self, data: Any) -> Dict[str, torch.Tensor]:
        """Derive analytic forces via autograd."""
        pos = data.pos
        orig_requires_grad = pos.requires_grad

        batch = getattr(data, "batch", None)
        if batch is None:
            batch = torch.zeros(pos.size(0), dtype=torch.long, device=pos.device)

        with torch.inference_mode(False), torch.enable_grad():
            pos_eval = pos.clone().detach().requires_grad_(True) if not orig_requires_grad else pos
            temp_data = ConformerData(
                pos=pos_eval,
                z=data.z,
                y=getattr(data, "y", torch.zeros((1, 1), device=pos.device)),
                weight=getattr(data, "weight", None),
                batch=batch,
            )
            preds = self.forward(temp_data)
            energy = preds["energy"]
            if not energy.requires_grad:
                forces = torch.zeros_like(pos_eval)
            else:
                grad_tuple = torch.autograd.grad(
                    outputs=energy.sum(),
                    inputs=pos_eval,
                    create_graph=self.training,
                    retain_graph=self.training,
                    allow_unused=True,
                )
                forces = -grad_tuple[0] if grad_tuple[0] is not None else torch.zeros_like(pos_eval)

        return {"energy": energy, "forces": forces}


# ==============================================================================
# 7. PyTorch Lightning Execution Orchestrator (GEOMTrainer)
# ==============================================================================

class GEOMTrainer(pl.LightningModule):
    """Standardized execution orchestrator for training 3D GNNs on geometric datasets.

    Connects the model layer (via ModelRegistry or direct injection), PhysicsInformedLoss,
    autograd force calculations, DDP synchronization, and OneCycleLR scheduling.
    """
    def __init__(
        self,
        model_name: str = "schnet",
        model_kwargs: Optional[Dict[str, Any]] = None,
        lr: float = DEFAULT_LR,
        weight_decay: float = DEFAULT_WEIGHT_DECAY,
        energy_weight: float = DEFAULT_ENERGY_WEIGHT,
        force_weight: float = DEFAULT_FORCE_WEIGHT,
        epochs: int = DEFAULT_MAX_EPOCHS,
        steps_per_epoch: int = DEFAULT_STEPS_PER_EPOCH,
        pct_start: float = DEFAULT_WARMUP_PCT,
        anneal_strategy: str = "cos",
        custom_model: Optional[nn.Module] = None,
        **kwargs: Any,
    ):
        super().__init__()
        # Saves hyperparameters to checkpoint and loggers automatically
        self.save_hyperparameters(ignore=["custom_model"])

        self.model_name = str(model_name).lower()
        kwargs_resolved = dict(model_kwargs or {})

        # Model Instantiation (Priority: custom_model > ModelRegistry > Built-in fallback)
        if custom_model is not None:
            self.model: nn.Module = custom_model
        else:
            try:
                self.model = ModelRegistry.build(self.model_name, **kwargs_resolved)
            except (KeyError, Exception) as exc:
                logger.info("Instantiating via built-in fallback for '%s': %s", self.model_name, exc)
                if "egnn" in self.model_name:
                    self.model = EquivariantGNNModel(
                        hidden_channels=kwargs_resolved.get("hidden_channels", 128),
                        num_layers=kwargs_resolved.get("num_layers", 6),
                        cutoff=kwargs_resolved.get("cutoff", 10.0),
                        max_z=kwargs_resolved.get("max_z", DEFAULT_MAX_Z),
                    )
                else:
                    self.model = SchNetModel(
                        hidden_channels=kwargs_resolved.get("hidden_channels", 128),
                        num_layers=kwargs_resolved.get("num_layers", 6),
                        num_radial=kwargs_resolved.get("num_radial", 32),
                        cutoff=kwargs_resolved.get("cutoff", DEFAULT_RBF_CUTOFF),
                        max_z=kwargs_resolved.get("max_z", DEFAULT_MAX_Z),
                    )

        self.loss_fn = PhysicsInformedLoss(energy_weight=energy_weight, force_weight=force_weight)
        self.compute_forces = float(force_weight) > 0.0

    def forward(self, data: Any) -> Dict[str, torch.Tensor]:
        """Route forward pass based on whether autograd forces are required."""
        if self.compute_forces:
            if hasattr(self.model, "compute_forces"):
                return self.model.compute_forces(data)
            pos = data.pos
            orig_grad = pos.requires_grad
            with torch.inference_mode(False), torch.enable_grad():
                pos_eval = pos.clone().detach().requires_grad_(True) if not orig_grad else pos
                temp_data = ConformerData(
                    pos=pos_eval,
                    z=data.z,
                    y=getattr(data, "y", torch.zeros((1, 1), device=pos.device)),
                    weight=getattr(data, "weight", None),
                    batch=getattr(data, "batch", None),
                )
                preds = self.model(temp_data)
                energy = preds["energy"]
                if not energy.requires_grad:
                    forces = torch.zeros_like(pos_eval)
                else:
                    grad_tuple = torch.autograd.grad(
                        outputs=energy.sum(),
                        inputs=pos_eval,
                        create_graph=self.training,
                        retain_graph=self.training,
                        allow_unused=True,
                    )
                    forces = -grad_tuple[0] if grad_tuple[0] is not None else torch.zeros_like(pos_eval)
            return {"energy": energy, "forces": forces}

        return self.model(data)

    def _shared_step(self, data: Any, batch_idx: int, stage: str) -> torch.Tensor:
        """Common forward evaluation and metric logging step."""
        preds = self(data)
        loss, metrics = self.loss_fn(preds, data)

        # Multi-GPU DDP metric synchronization rule
        sync = (stage != "train")
        batch_size = getattr(data, "num_graphs", None)
        if batch_size is None:
            batch_vec = getattr(data, "batch", None)
            batch_size = int(batch_vec.max().item() + 1) if batch_vec is not None and batch_vec.numel() > 0 else 1

        if getattr(self, "_trainer", None) is not None:
            for key, val in metrics.items():
                self.log(
                    f"{stage}/{key}",
                    val,
                    batch_size=batch_size,
                    sync_dist=sync,
                    on_epoch=True,
                    prog_bar=(key == "loss"),
                )

        return loss

    def training_step(self, data: Any, batch_idx: int) -> torch.Tensor:
        """Execute single training optimization step."""
        return self._shared_step(data, batch_idx, "train")

    def validation_step(self, data: Any, batch_idx: int) -> torch.Tensor:
        """Execute single validation step.

        CRITICAL ARCHITECTURAL CONTRACT: PyTorch Lightning disables gradients globally in validation.
        Analytical forces (-dE/dX) strictly require coordinate gradients. We locally enable autograd.
        """
        if self.compute_forces:
            with torch.inference_mode(False), torch.set_grad_enabled(True):
                if hasattr(data, "pos") and isinstance(data.pos, torch.Tensor):
                    data.pos = data.pos.clone().detach().requires_grad_(True)
                return self._shared_step(data, batch_idx, "val")
        return self._shared_step(data, batch_idx, "val")

    def test_step(self, data: Any, batch_idx: int) -> torch.Tensor:
        """Execute single test step with autograd force derivation support."""
        if self.compute_forces:
            with torch.inference_mode(False), torch.set_grad_enabled(True):
                if hasattr(data, "pos") and isinstance(data.pos, torch.Tensor):
                    data.pos = data.pos.clone().detach().requires_grad_(True)
                return self._shared_step(data, batch_idx, "test")
        return self._shared_step(data, batch_idx, "test")

    def configure_optimizers(self) -> Dict[str, Any]:
        """Configure AdamW optimizer and OneCycleLR (Cosine Annealing with Warmup) schedule.

        Segregates weight decay: applies decay to 2D+ weight matrices while setting decay to 0.0
        for 1D biases, LayerNorm parameters, and atomic embedding vectors.
        """
        decay_params: List[torch.nn.Parameter] = []
        no_decay_params: List[torch.nn.Parameter] = []

        for name, param in self.model.named_parameters():
            if not param.requires_grad:
                continue
            if param.ndim < 2 or "bias" in name or "embedding" in name or "norm" in name:
                no_decay_params.append(param)
            else:
                decay_params.append(param)

        optimizer_groups = [
            {"params": decay_params, "weight_decay": float(self.hparams.weight_decay)},
            {"params": no_decay_params, "weight_decay": 0.0},
        ]

        optimizer = AdamW(optimizer_groups, lr=float(self.hparams.lr))

        total_steps = max(100, int(self.hparams.epochs) * int(self.hparams.steps_per_epoch))
        pct_start = float(self.hparams.get("pct_start", DEFAULT_WARMUP_PCT))

        scheduler = OneCycleLR(
            optimizer,
            max_lr=float(self.hparams.lr),
            total_steps=total_steps,
            pct_start=pct_start,
            anneal_strategy=str(self.hparams.get("anneal_strategy", "cos")),
            cycle_momentum=False,
        )

        return {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": scheduler,
                "interval": "step",
                "frequency": 1,
            },
        }


# Dynamic Alias for backward compatibility
GEOMLightningModule = GEOMTrainer
