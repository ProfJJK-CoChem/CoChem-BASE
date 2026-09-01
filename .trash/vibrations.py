import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path

class MatplotlibVibrationalPlotter:
    """
    Plots vibrational normal modes using Matplotlib.
    """
    def __init__(self, default_dpi: int = 150) -> None:
        """Initialize the plotter."""
        self.default_dpi = default_dpi
        self.figure_size = (10, 8)

    def render_normal_mode_plot(
        self,
        geometry: np.ndarray,
        hessian: np.ndarray,
        masses: np.ndarray,
        output_image: str | Path,
        mode_idx: int = 6
    ) -> bool:
        """
        Renders a 3D quiver plot for a specified normal mode displacement vector.

        Args:
            geometry: Cartesian coordinates of shape (N, 3).
            hessian: Hessian matrix of shape (3N, 3N).
            masses: Atomic masses of shape (N,).
            output_image: Output path for the generated plot.
            mode_idx: The index of the vibrational mode to plot (default 6).

        Returns:
            bool: True if the plot was generated successfully.
        """
        geom = np.array(geometry, dtype=float)
        H = np.array(hessian, dtype=float)
        M = np.array(masses, dtype=float)

        N = len(geom)
        if geom.shape != (N, 3):
            raise ValueError(f"geometry shape must be (N, 3), got {geom.shape}")
        if H.shape != (3 * N, 3 * N):
            raise ValueError(f"hessian shape must be (3*N, 3*N), got {H.shape}")
        if len(M) != N:
            raise ValueError(f"masses length must be {N}, got {len(M)}")
        if np.any(M <= 0):
            raise ValueError("all masses must be greater than 0")

        # Mass-weight the Hessian
        M_vec = np.repeat(np.sqrt(M), 3)
        M_inv = np.diag(1.0 / M_vec)
        H_mw = M_inv @ H @ M_inv

        eigenvalues, eigenvectors = np.linalg.eigh(H_mw)
        # Sort
        idx = np.argsort(eigenvalues)
        eigenvectors = eigenvectors[:, idx]

        # Mode vector (mass-weighted coordinates)
        q_i = eigenvectors[:, mode_idx]

        # Un-mass-weighting: x_i = q_i / sqrt(m_i)
        x_i = q_i / M_vec
        mode_vec = x_i.reshape((N, 3))
        
        # Normalise the resulting displacement vectors for plotting
        norm = np.linalg.norm(mode_vec)
        if norm > 0:
            mode_vec = mode_vec / norm

        output_path = Path(output_image)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fig = plt.figure(figsize=(10, 8), dpi=150)
        ax = fig.add_subplot(111, projection='3d')
        ax.set_facecolor('#0f172a')
        fig.patch.set_facecolor('#0f172a')

        try:
            # Plot atoms
            ax.scatter(geom[:, 0], geom[:, 1], geom[:, 2], color='#38bdf8', s=200, edgecolors='white', linewidths=1.5, label='Atoms')

            # Plot normal mode displacement vectors
            ax.quiver(
                geom[:, 0], geom[:, 1], geom[:, 2],
                mode_vec[:, 0], mode_vec[:, 1], mode_vec[:, 2],
                color='#f43f5e', length=0.8, normalize=True, linewidth=2.5, label='Mode Vectors'
            )

            ax.set_title("Vibrational Normal Mode Vectors", color='white', fontsize=14, pad=20)
            ax.set_xlabel("X (Å)", color='white')
            ax.set_ylabel("Y (Å)", color='white')
            ax.set_zlabel("Z (Å)", color='white')
            ax.tick_params(colors='white')
            ax.legend(facecolor='#1e293b', edgecolor='none', labelcolor='white')
            plt.tight_layout()

            plt.savefig(output_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        finally:
            plt.close(fig)

        return output_path.exists() and output_path.stat().st_size > 0


WebGLVectorViewer = MatplotlibVibrationalPlotter
