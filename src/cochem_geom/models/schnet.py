"""CoChem-GEOM: SchNet Invariant Continuous-Filter Convolutional Neural Network.
=============================================================================
Provides production-grade implementation of the SchNet architecture (Schütt et al., 2017)
for 3D molecular conformers, potential energy surface (PES) modeling, and analytical
force field derivation within the CoChem ecosystem (CoChem-GEOM and CoChem-BASE).

Theoretical Foundations & Physics Contracts:
1. Continuous-Filter Convolutions (CFConv) over Invariant Scalar Distances:
   - Scalar Euclidean interatomic distances $d_{ij} = \\|\\mathbf{r}_i - \\mathbf{r}_j\\|_2$
     are strictly invariant under global $E(3)$ transformations (rotations $\\mathrm{SO}(3)$
     and translations $\\mathbb{R}^3$) [M]:
     $$d_{ij}(\\mathbf{r} \\mathbf{R}^T + \\mathbf{t}) = d_{ij}(\\mathbf{r})$$
   - Distances are expanded into continuous Gaussian radial basis functions (RBF)
     and modulated by a smooth cosine cutoff envelope $f_{\\text{cut}}(d_{ij})$ [D]:
     $$W(d_{ij}) = \\text{MLP}_{\\text{filter}}(\\boldsymbol{\\phi}(d_{ij})) \\cdot f_{\\text{cut}}(d_{ij})$$
   - Message passing executes continuous convolutions with extensive additive aggregation:
     $$\\mathbf{m}_i = \\sum_{j \\in \\mathcal{N}(i)} W(d_{ij}) \\odot \\text{Linear}(\\mathbf{h}_j) \\quad [\\text{M}]$$
     $$\\mathbf{h}'_i = \\mathbf{h}_i + \\text{MLP}_{\\text{update}}(\\mathbf{m}_i) \\quad [\\text{D}]$$

2. Symmetries & Conservation Laws:
   - Scalar electronic potential energy $E \\in \\mathbb{R}$ is strictly $E(3)$-invariant:
     $$E(\\mathbf{r} \\mathbf{R}^T + \\mathbf{t}) = E(\\mathbf{r}) \\quad [\\text{M}]$$
   - Analytical interatomic forces $\\mathbf{F} = -\\nabla_{\\mathbf{r}} E$ transform equivariantly:
     $$\\mathbf{F}(\\mathbf{r} \\mathbf{R}^T + \\mathbf{t}) = \\mathbf{F}(\\mathbf{r}) \\mathbf{R}^T \\quad [\\text{D}]$$
   - Net force vanishes for isolated molecular systems: $\\sum_{i=1}^N \\mathbf{F}_i = \\mathbf{0}$ [M].

3. Twice-Continuous Differentiability ($C^2$) & Autograd Force Derivation:
   - All activation functions are smooth $\\text{SiLU}(x) = x \\cdot \\sigma(x)$ [M].
   - Distance norm calculations use minimum clamping (`clamp_min(1e-6)`) to prevent
     NaN / Inf gradient singularities when coordinates approach zero distance [D].

4. Strict Architectural Mandates:
   - Strict Zero-Mock Mandate: 100% authentic PyTorch geometric tensor mathematics (no stubs/mocks).
   - Provenance Tagging: Explicitly tagged with [M] (Measured), [D] (Derived), [E] (Expert Estimate).
   - BaseGNN API Compliance: Full compatibility with dynamic model registry and force calculus.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn
from torch_geometric.nn import MessagePassing

from cochem_geom.data.pyg_schema import ConformerData
from cochem_geom.models.base_gnn import (
    DEFAULT_HIDDEN_CHANNELS,
    DEFAULT_MAX_Z,
    BaseGNN,
    GNNModelConfig,
    build_radius_graph,
    extract_gnn_inputs,
)
from cochem_geom.models.layers.interaction import CosineCutoff
from cochem_geom.models.layers.radial_basis import GaussianSmearing
from cochem_geom.models.layers.readout import EnergyReadout
from cochem_geom.models.registry import ModelRegistry


def _dynamic_radius_graph(
    pos: torch.Tensor,
    r: float,
    batch: Optional[torch.Tensor] = None,
    max_num_neighbors: int = 64,
) -> torch.Tensor:
    """Compute dynamic radius graph with robust fallback [D]."""
    try:
        from torch_geometric.nn import radius_graph as pyg_radius_graph
        return pyg_radius_graph(
            pos,
            r=r,
            batch=batch,
            loop=False,
            max_num_neighbors=max_num_neighbors,
        )
    except (ImportError, RuntimeError):
        edge_index, _ = build_radius_graph(
            pos=pos,
            batch=batch,
            cutoff=r,
            max_num_neighbors=max_num_neighbors,
        )
        return edge_index


class SchNetInteraction(MessagePassing):
    """Continuous-filter convolutional interaction block for SchNet [D].

    Computes spatial convolutions strictly over invariant scalar distances:
    $$\\mathbf{h}'_i = \\mathbf{h}_i + \\text{MLP}_{\\text{update}}\\left( \\sum_{j \\in \\mathcal{N}(i)} W(d_{ij}) \\odot \\text{Linear}(\\mathbf{h}_j) \\right)$$
    where $W(d_{ij}) = \\text{MLP}_{\\text{filter}}(\\boldsymbol{\\phi}(d_{ij})) \\cdot f_{\\text{cut}}(d_{ij})$.

    Parameters
    ----------
    hidden_channels : int
        Dimension of latent node feature representations (default: 128) [E].
    num_gaussians : int
        Number of Gaussian radial basis kernels (default: 50) [E].
    cutoff : float
        Spatial interaction cutoff radius in Angstroms (default: 10.0) [M].
    """

    def __init__(
        self,
        hidden_channels: int = 128,
        num_gaussians: int = 50,
        cutoff: float = 10.0,
    ) -> None:
        # Physics Constraint: Extensive properties require additive aggregation [M]
        super().__init__(aggr="add", node_dim=0)
        self.hidden_channels: int = int(hidden_channels)
        self.num_gaussians: int = int(num_gaussians)
        self.cutoff: float = float(cutoff)

        # Filter Generator: maps RBF distance expansions to hidden filter weights
        self.mlp_filter: nn.Sequential = nn.Sequential(
            nn.Linear(self.num_gaussians, self.hidden_channels),
            nn.SiLU(),  # Smooth activation required for continuous force derivatives [M]
            nn.Linear(self.hidden_channels, self.hidden_channels),
        )

        # Linear mapping of source node states before continuous convolution
        self.lin: nn.Linear = nn.Linear(self.hidden_channels, self.hidden_channels)

        # Updates the recipient node state after continuous message aggregation
        self.update_mlp: nn.Sequential = nn.Sequential(
            nn.Linear(self.hidden_channels, self.hidden_channels),
            nn.SiLU(),
            nn.Linear(self.hidden_channels, self.hidden_channels),
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_weight: torch.Tensor,
        edge_attr: torch.Tensor,
    ) -> torch.Tensor:
        """Execute interaction message passing step immutably [D].

        Parameters
        ----------
        x : torch.Tensor
            Node embeddings of shape `[N, hidden_channels]`.
        edge_index : torch.Tensor
            Pairwise directed edge indices `[2, E]` (src, dst).
        edge_weight : torch.Tensor
            Cosine cutoff envelope weights `[E]` or `[E, 1]`.
        edge_attr : torch.Tensor
            Gaussian RBF expanded distances `[E, num_gaussians]`.

        Returns
        -------
        torch.Tensor
            Updated invariant node representations `[N, hidden_channels]`.
        """
        if edge_index.size(1) == 0:
            return x

        x_lin = self.lin(x)

        # Ensure cutoff envelope has trailing dimension for broadcasting: [E, 1]
        w_envelope = edge_weight if edge_weight.dim() == 2 else edge_weight.unsqueeze(-1)

        # Filter Generation: Map RBF to hidden dim and apply physical boundary cutoff
        w = self.mlp_filter(edge_attr) * w_envelope

        # PyG propagate implicitly calls self.message(), then aggregates via aggr='add'
        m = self.propagate(edge_index, x=x_lin, W=w, size=(x.size(0), x.size(0)))

        # Residual connection prevents gradient vanishing
        return x + self.update_mlp(m)

    def message(self, x_j: torch.Tensor, W: torch.Tensor) -> torch.Tensor:
        """Continuous convolution: element-wise multiplication of source features and filter weights [D].

        Parameters
        ----------
        x_j : torch.Tensor
            Source node representations `[E, hidden_channels]`.
        W : torch.Tensor
            Filter weights modulated by cutoff envelope `[E, hidden_channels]`.

        Returns
        -------
        torch.Tensor
            Continuous convolutional messages `[E, hidden_channels]`.
        """
        return x_j * W


@ModelRegistry.register("schnet")
class SchNet(BaseGNN):
    """Production-grade Continuous-Filter Convolutional Neural Network (SchNet) [D].

    Implements the invariant SchNet architecture (Schütt et al., 2017) adhering strictly
    to the BaseGNN API, E(3) symmetry constraints, and Zero-Mock mandate.

    Parameters
    ----------
    hidden_channels : int
        Dimension of latent node representations (default: 128) [E].
    num_interactions : int
        Number of continuous-filter interaction blocks (default: 6) [E].
    num_gaussians : int
        Number of Gaussian radial basis kernels (default: 50) [E].
    cutoff : float
        Spatial interaction cutoff radius in Angstroms (default: 10.0) [M].
    max_z : int
        Maximum supported atomic number Z (default: 100) [D].
    max_num_neighbors : int
        Maximum allowable neighbors per node in radius graph (default: 64) [E].
    config : Optional[Union[GNNModelConfig, Dict[str, Any]]]
        Optional configuration schema object or dictionary.
    """

    def __init__(
        self,
        hidden_channels: int = 128,
        num_interactions: int = 6,
        num_gaussians: int = 50,
        cutoff: float = 10.0,
        max_z: int = 100,
        max_num_neighbors: int = 64,
        config: Optional[Union[GNNModelConfig, Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> None:
        if config is not None:
            if isinstance(config, GNNModelConfig):
                hidden_channels = config.hidden_channels
                num_interactions = config.num_layers
                num_gaussians = config.num_radial
                cutoff = config.cutoff
                max_z = config.max_z
            elif isinstance(config, dict):
                hidden_channels = config.get("hidden_channels", hidden_channels)
                num_interactions = config.get(
                    "num_interactions", config.get("num_layers", num_interactions)
                )
                num_gaussians = config.get(
                    "num_gaussians", config.get("num_radial", num_gaussians)
                )
                cutoff = config.get("cutoff", cutoff)
                max_z = config.get("max_z", max_z)
                max_num_neighbors = config.get("max_num_neighbors", max_num_neighbors)

        super().__init__(hidden_channels=hidden_channels, max_z=max_z)
        self.num_interactions: int = int(num_interactions)
        self.num_gaussians: int = int(num_gaussians)
        self.cutoff: float = float(cutoff)
        self.max_num_neighbors: int = int(max_num_neighbors)

        # Mathematical Primitives (Task 5 / layers)
        self.distance_expansion: GaussianSmearing = GaussianSmearing(
            start=0.0,
            stop=self.cutoff,
            num_gaussians=self.num_gaussians,
        )
        self.cutoff_network: CosineCutoff = CosineCutoff(cutoff=self.cutoff)

        self.interactions: nn.ModuleList = nn.ModuleList([
            SchNetInteraction(
                hidden_channels=self.hidden_channels,
                num_gaussians=self.num_gaussians,
                cutoff=self.cutoff,
            )
            for _ in range(self.num_interactions)
        ])

        self.readout: EnergyReadout = EnergyReadout(hidden_channels=self.hidden_channels)

    def forward(
        self,
        data: Union[ConformerData, Dict[str, Any], Any],
    ) -> Dict[str, torch.Tensor]:
        """Forward pass predicting total molecular electronic potential energy [D].

        Parameters
        ----------
        data : Union[ConformerData, Dict[str, Any], Any]
            Molecular graph data structure containing coordinates `pos` and atomic numbers `z`.

        Returns
        -------
        Dict[str, torch.Tensor]
            Dictionary containing mandatory key `"energy"` of shape `[Batch_Size, 1]`.
        """
        pos, z, batch, _, _ = extract_gnn_inputs(data)

        # 0. Initial Atomic Embedding: map discrete atomic numbers Z to latent representations
        x = self.atom_embedding(z)

        # 1. Dynamic Radius Graph Calculation on the fly
        edge_index = _dynamic_radius_graph(
            pos,
            r=self.cutoff,
            batch=batch,
            max_num_neighbors=self.max_num_neighbors,
        )

        if edge_index.size(1) > 0:
            row, col = edge_index[0], edge_index[1]

            # 2. Extract strictly invariant distance scalars
            # clamp_min(1e-6) prevents NaN gradients during autograd force calculus [D]
            dist_vec = pos[row] - pos[col]
            distances = torch.linalg.norm(dist_vec, dim=-1).clamp_min(1e-6)

            # 3. Apply structural primitives
            edge_attr = self.distance_expansion(distances)
            edge_weight = self.cutoff_network(distances)

            # 4. Message Passing through continuous-filter convolution blocks
            for interaction in self.interactions:
                x = interaction(x, edge_index, edge_weight, edge_attr)

        # 5. Global Energy Readout using extensive additive pooling
        energy = self.readout(x, batch)

        return {"energy": energy}


# Register uppercase alias in ModelRegistry
ModelRegistry.register("SchNet")(SchNet)

__all__ = [
    "SchNet",
    "SchNetInteraction",
]
