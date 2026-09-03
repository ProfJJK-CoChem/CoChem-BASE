"""Scale-Invariant Loss Landscape Visualization Engine (REQ-TORQ-TRAIN-095 [D]).

Implements the filter-normalized perturbation scheme of Li et al. (2018):
    theta(alpha, beta) = theta* + alpha * d1 + beta * d2
where directions are normalized per filter/layer to match the Frobenius norm of theta*:
    d_{k, j} = (v_{k, j} / ||v_{k, j}||_F) * ||theta^*_j||_F
"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn

from Libraries.cochem_torq_training_schemas import LossLandscapeConfig


def generate_filter_normalized_direction(
    model: nn.Module,
    seed: Optional[int] = None,
) -> Dict[str, torch.Tensor]:
    """Generate a random perturbation vector matching per-filter Frobenius norms. [D]"""
    if seed is not None:
        torch.manual_seed(seed)

    direction: Dict[str, torch.Tensor] = {}

    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue

        p_data = param.data
        v = torch.randn_like(p_data)

        if p_data.dim() >= 2:
            # Per-filter normalization along outer dimension (output channels/units)
            norm_p = torch.norm(p_data.view(p_data.size(0), -1), dim=1, keepdim=True)
            norm_v = torch.norm(v.view(v.size(0), -1), dim=1, keepdim=True)
            # Expand to match tensor shape
            for _ in range(p_data.dim() - 2):
                norm_p = norm_p.unsqueeze(-1)
                norm_v = norm_v.unsqueeze(-1)
            norm_v = torch.clamp(norm_v, min=1e-12)
            d = (v / norm_v) * norm_p
        else:
            # 1D tensors (e.g. bias vectors)
            norm_p = torch.norm(p_data)
            norm_v = torch.norm(v)
            norm_v = max(float(norm_v.item()), 1e-12)
            d = (v / norm_v) * norm_p

        direction[name] = d

    return direction


def generate_orthogonal_filter_directions(
    model: nn.Module,
    seed: Optional[int] = None,
) -> Tuple[Dict[str, torch.Tensor], Dict[str, torch.Tensor]]:
    """Generate two filter-normalized perturbation directions d1 and d2. [D]"""
    seed1 = seed if seed is not None else 1001
    seed2 = (seed + 1) if seed is not None else 2002
    d1 = generate_filter_normalized_direction(model, seed=seed1)
    d2 = generate_filter_normalized_direction(model, seed=seed2)
    return d1, d2


def set_perturbed_weights(
    model: nn.Module,
    base_params: Dict[str, torch.Tensor],
    d1: Dict[str, torch.Tensor],
    alpha: float,
    d2: Optional[Dict[str, torch.Tensor]] = None,
    beta: float = 0.0,
) -> None:
    """Perturb model weights in-place: theta = theta* + alpha * d1 + beta * d2. [D]"""
    with torch.no_grad():
        for name, param in model.named_parameters():
            if name in base_params and name in d1:
                perturbed = base_params[name] + alpha * d1[name]
                if d2 is not None and name in d2:
                    perturbed = perturbed + beta * d2[name]
                param.data.copy_(perturbed)


def restore_base_weights(
    model: nn.Module,
    base_params: Dict[str, torch.Tensor],
) -> None:
    """Restore unperturbed parameter tensors theta* in-place. [M]"""
    with torch.no_grad():
        for name, param in model.named_parameters():
            if name in base_params:
                param.data.copy_(base_params[name])


def compute_1d_loss_surface(
    model: nn.Module,
    eval_loss_fn: Callable[[], float],
    d1: Dict[str, torch.Tensor],
    alpha_values: Sequence[float],
) -> List[float]:
    """Profile loss along 1D normalized direction alpha with VRAM/RAM isolation. [M]"""
    base_params = {name: param.data.clone() for name, param in model.named_parameters() if param.requires_grad}
    losses: List[float] = []

    model.eval()
    with torch.no_grad():
        for alpha in alpha_values:
            set_perturbed_weights(model, base_params, d1, alpha=float(alpha))
            loss = eval_loss_fn()
            losses.append(loss)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

        restore_base_weights(model, base_params)

    return losses


def compute_2d_loss_grid(
    model: nn.Module,
    eval_loss_fn: Callable[[], float],
    d1: Dict[str, torch.Tensor],
    d2: Dict[str, torch.Tensor],
    config: LossLandscapeConfig,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute 2D loss surface across equidistant grid (alpha, beta) in [range_min, range_max]. [M]"""
    base_params = {name: param.data.clone() for name, param in model.named_parameters() if param.requires_grad}

    res = config.grid_resolution
    t_alphas = torch.linspace(config.range_min, config.range_max, res, dtype=torch.float64)
    t_betas = torch.linspace(config.range_min, config.range_max, res, dtype=torch.float64)
    t_beta_grid, t_alpha_grid = torch.meshgrid(t_betas, t_alphas, indexing="ij")
    alpha_grid = t_alpha_grid.numpy()
    beta_grid = t_beta_grid.numpy()
    loss_tensor = torch.empty((res, res), dtype=torch.float64)

    model.eval()
    with torch.no_grad():
        for i in range(res):
            for j in range(res):
                a = float(alpha_grid[i, j])
                b = float(beta_grid[i, j])
                set_perturbed_weights(model, base_params, d1, alpha=a, d2=d2, beta=b)
                loss_tensor[i, j] = eval_loss_fn()

            # VRAM / Memory reclamation after each row
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

        restore_base_weights(model, base_params)

    loss_grid = loss_tensor.numpy()
    return alpha_grid, beta_grid, loss_grid


def render_loss_contour_plot(
    alpha_grid: np.ndarray,
    beta_grid: np.ndarray,
    loss_grid: np.ndarray,
    output_path: Path,
    title: str = "Filter-Normalized MLFF Loss Landscape",
) -> Path:
    """Render high-resolution 2D contour plot and write to disk using Agg backend. [M]"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)
    # Log scale contour levels if dynamic range is large, else linear levels
    min_l = float(np.min(loss_grid))
    max_l = float(np.max(loss_grid))

    if max_l > min_l > 0 and (max_l / min_l) > 100:
        levels = np.geomspace(min_l, max_l, 35)
    else:
        levels = torch.linspace(min_l, max_l, 35, dtype=torch.float64).numpy()

    cs = ax.contourf(alpha_grid, beta_grid, loss_grid, levels=levels, cmap="viridis", extend="both")
    ax.contour(alpha_grid, beta_grid, loss_grid, levels=levels[::3], colors="black", linewidths=0.5, alpha=0.6)
    # Plot center optimum marker
    ax.plot(0.0, 0.0, marker="x", color="red", markersize=10, markeredgewidth=2, label=r"Converged $\theta^*$")

    cbar = fig.colorbar(cs, ax=ax)
    cbar.set_label("Loss (Hartree)", fontsize=11)

    ax.set_xlabel(r"$\alpha$ (Direction 1)", fontsize=12)
    ax.set_ylabel(r"$\beta$ (Direction 2)", fontsize=12)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    return output_path
