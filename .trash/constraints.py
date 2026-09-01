from __future__ import annotations

import logging
from typing import Any
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

class ConstraintError(Exception):
    """Exception raised for constraint-related errors in the engine."""
    pass

class ConstraintEngine:
    """
    Applies geometry and gradient constraints to a molecular system.
    """
    def __init__(self) -> None:
        """Initialize the ConstraintEngine with an empty list of frozen bonds."""
        self.frozen_bonds: list[tuple[int, int, float]] = []

    def freeze_bond(self, i: int, j: int, distance: float) -> None:
        """
        Freeze the distance between atoms i and j.
        
        Args:
            i: Index of the first atom.
            j: Index of the second atom.
            distance: Target distance between the two atoms.
            
        Raises:
            ConstraintError: If indices are the same or distance is not strictly positive.
        """
        if i == j:
            raise ConstraintError(f"Cannot freeze a bond between the same atom (index {i}).")
        if distance <= 0:
            raise ConstraintError(f"Bond distance must be positive, got {distance}.")
        self.frozen_bonds.append((i, j, float(distance)))

    def apply_gradient_projection(
        self, geometry: NDArray[np.float64], gradients: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """
        Project gradients to satisfy bond constraints.
        
        Args:
            geometry: The atomic coordinates of shape (N, 3).
            gradients: The atomic gradients of shape (N, 3).
            
        Returns:
            The constrained gradients of shape (N, 3).
            
        Raises:
            ConstraintError: If geometry or gradient shapes are incompatible.
        """
        if geometry.ndim != 2 or geometry.shape[1] != 3:
            raise ConstraintError("Geometry must have shape (N, 3).")
        if gradients.shape != geometry.shape:
            raise ConstraintError("Gradients shape must match geometry shape.")
        n_atoms = geometry.shape[0]

        corr_grad = gradients.copy()
        for i, j, _ in self.frozen_bonds:
            if i >= n_atoms or j >= n_atoms or i < 0 or j < 0:
                raise ConstraintError(f"Atom indices {i}, {j} out of bounds for geometry size {n_atoms}.")
                
            diff = geometry[j] - geometry[i]
            dist_val = float(np.sqrt(np.sum(diff * diff)))
            if dist_val < 1e-12:
                continue
            u = diff / dist_val
            # Fix relative gradient projection along the constraint normal
            delta_g = 0.5 * np.dot(corr_grad[j] - corr_grad[i], u) * u
            corr_grad[i] += delta_g
            corr_grad[j] -= delta_g
        return corr_grad

    def enforce_constraints(self, geometry: NDArray[np.float64]) -> NDArray[np.float64]:
        """
        Iteratively enforce geometry constraints (SHAKE-like).
        
        Args:
            geometry: The atomic coordinates of shape (N, 3).
            
        Returns:
            The constrained atomic coordinates of shape (N, 3).
            
        Raises:
            ConstraintError: If geometry shape is invalid or constraints do not converge.
        """
        if geometry.ndim != 2 or geometry.shape[1] != 3:
            raise ConstraintError("Geometry must have shape (N, 3).")
        n_atoms = geometry.shape[0]
        
        new_geom = geometry.copy()
        
        if not self.frozen_bonds:
            return new_geom
            
        # Validate indices
        for i, j, _ in self.frozen_bonds:
            if i >= n_atoms or j >= n_atoms or i < 0 or j < 0:
                raise ConstraintError(f"Atom indices {i}, {j} out of bounds for geometry size {n_atoms}.")

        tol = 1e-8
        max_iter = 100
        
        for _ in range(max_iter):
            max_dev = 0.0
            for i, j, target_dist in self.frozen_bonds:
                diff = new_geom[j] - new_geom[i]
                current_dist = float(np.sqrt(np.sum(diff * diff)))
                dev = abs(current_dist - target_dist)
                if dev > max_dev:
                    max_dev = dev
                    
                if current_dist < 1e-12:
                    continue
                    
                u = diff / current_dist
                correction = 0.5 * (current_dist - target_dist) * u
                new_geom[i] += correction
                new_geom[j] -= correction
                
            if max_dev < tol:
                break
        else:
            logger.warning("Constraints did not fully converge within max iterations.")
            
        return new_geom
