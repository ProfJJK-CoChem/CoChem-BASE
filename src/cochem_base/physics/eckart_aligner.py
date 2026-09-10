"""
CoChem Eckart Frame Aligner & Translational Normalization Engine.
WBS 1.3.1: Mass-Weighted Center-of-Mass Vector Accumulator (Subsystem VR01-SS2)

Governing Specifications:
- Method Matrix v4.1 (§10.1–10.8, §9A.1–9A.5)
- Council Emergency Session 012/013 Resolutions (COCHEM-COUNCIL-RES-013-ZERO-TRUST-DISPATCH)
- Invariant VR-01-T01: delta_COM = ||sum(m_i * r_tilde_i)||_2 < 1e-12 u*Angstrom
- Dynamic Mendeleev Mandate: Zero static mass dictionaries; dynamic nuclide resolution via disambiguate_mass()
- High-Performance Vectorization: Pure NumPy broadcasting (<15 µs execution for N=100)
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple, Union
import numpy as np

try:
    from cochem_base.exceptions import CoChemError
except ImportError:
    class CoChemError(Exception):
        """Fallback root exception if cochem_base.exceptions is unavailable."""
        pass

from cochem_base.physics.nuclide_resolver import disambiguate_mass


# ============================================================================
# Exception Hierarchy (WBS 1.3.1.3.2)
# ============================================================================

class NumericalInvariantBreach(CoChemError):
    """Base exception raised when a physical or numerical invariant is violated."""
    pass


class COMResidualError(NumericalInvariantBreach, ValueError):
    """Raised when the mass-weighted center of mass residual norm violates Invariant VR-01-T01."""

    def __init__(self, message: str = "", residual_norm: Optional[float] = None) -> None:
        super().__init__(message)
        self.residual_norm = residual_norm


class SO3ClosureError(NumericalInvariantBreach, ValueError):
    """Raised when rotation matrix violates proper rotation group SO(3) closure (Invariant VR-01-R01)."""
    pass


class EckartResidualError(NumericalInvariantBreach, ValueError):
    """Raised when Eckart residual violates Invariant VR-01-R02 (||L_Eckart|| < 1e-10)."""
    pass


class CollinearDegeneracyError(NumericalInvariantBreach, ValueError):
    """Raised when collinear or planar degeneracy cannot be resolved."""
    pass


# ============================================================================
# Core Vectorized COM Accumulator (WBS 1.3.1.1)
# ============================================================================

def compute_center_of_mass(
    coordinates: np.ndarray,
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
) -> np.ndarray:
    """Compute the mass-weighted center of mass (COM) vector for a molecular system.

    Supports unbatched geometries of shape (N, 3) and batched tensors of shape (B, N, 3).
    Atomic masses are either explicitly provided or dynamically resolved via the
    authoritative dynamic Mendeleev nuclide resolver.

    Mathematical formulation:
        R_COM = (1 / M_total) * sum_{i=1}^N m_i * r_i, where M_total = sum_{i=1}^N m_i

    Args:
        coordinates: Molecular coordinates of shape (N, 3) or (B, N, 3) in Angstroms.
        masses: Optional sequence or numpy array of atomic masses in unified atomic mass units (u).
            For unbatched shape (N, 3), masses must have shape (N,).
            For batched shape (B, N, 3), masses can have shape (N,) or (B, N).
        symbols: Optional sequence of IUPAC nuclide symbols (e.g. ['O', 'H', 'H']).
            Required if masses is None.

    Returns:
        Center of mass vector as np.float64 array:
            shape (3,) for unbatched coordinates (N, 3),
            shape (B, 3) for batched coordinates (B, N, 3).

    Raises:
        TypeError: If coordinates or symbols have invalid types.
        ValueError: If input dimensions are invalid, non-Cartesian (last dim != 3),
            coordinates contain NaN or Inf, masses are missing or contain non-positive values,
            or symbols count does not match atom count.
    """
    if isinstance(coordinates, np.ndarray) and coordinates.dtype == np.float64:
        coords = coordinates
    else:
        if not isinstance(coordinates, (np.ndarray, list, tuple)):
            raise TypeError(
                f"Coordinates must be an array-like structure, got {type(coordinates).__name__}."
            )
        try:
            coords = np.asarray(coordinates, dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Coordinates could not be converted to float64 array: {exc}") from exc

    ndim = coords.ndim
    if ndim not in (2, 3):
        raise ValueError(
            f"Coordinates must have 2 or 3 dimensions: (N, 3) or (B, N, 3), got shape {coords.shape} ({ndim}D)."
        )
    if coords.shape[-1] != 3:
        raise ValueError(
            f"Last dimension of coordinates must be 3 (Cartesian x, y, z), got {coords.shape[-1]}."
        )
    n_atoms = coords.shape[-2]
    if n_atoms == 0:
        raise ValueError("Coordinate array must contain at least 1 atom (N >= 1).")
    if ndim == 3 and coords.shape[0] == 0:
        raise ValueError("Batch coordinate tensor must contain at least 1 structure (B >= 1).")
    if not np.isfinite(coords.sum()):
        raise ValueError("Coordinates must not contain NaN or Inf values.")

    # Mass resolution
    if masses is None:
        if symbols is None:
            raise ValueError("Either 'masses' or 'symbols' must be provided to compute center of mass.")
        if isinstance(symbols, str):
            raise TypeError("Symbols must be a sequence of nuclide strings, not a single string.")
        if len(symbols) != n_atoms:
            raise ValueError(
                f"Number of chemical symbols ({len(symbols)}) does not match number of atoms ({n_atoms})."
            )
        resolved_masses = [disambiguate_mass(s) for s in symbols]
        mass_arr = np.asarray(resolved_masses, dtype=np.float64)
    else:
        if isinstance(masses, np.ndarray) and masses.dtype == np.float64:
            mass_arr = masses
        else:
            try:
                mass_arr = np.asarray(masses, dtype=np.float64)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Masses could not be converted to float64 array: {exc}") from exc

        if mass_arr.size == 0:
            raise ValueError("Masses array must not be empty.")
        if not np.isfinite(mass_arr.sum()):
            raise ValueError("Masses must not contain NaN or Inf values.")

    if ndim == 2:
        if mass_arr.ndim == 1:
            if mass_arr.shape[0] != n_atoms:
                raise ValueError(
                    f"Masses length ({mass_arr.shape[0]}) does not match number of atoms ({n_atoms})."
                )
        elif mass_arr.ndim == 2 and mass_arr.shape == (n_atoms, 1):
            mass_arr = mass_arr.reshape(-1)
        else:
            raise ValueError(
                f"For unbatched coordinates of shape {coords.shape}, masses must have shape ({n_atoms},), got {mass_arr.shape}."
            )
        if np.any(mass_arr <= 0.0):
            raise ValueError("All individual atomic masses must be strictly positive (> 0).")

        total_mass = float(np.sum(mass_arr))
        if total_mass <= 0.0:
            raise ValueError("Total molecular mass must be strictly positive (> 0).")
        r_com = (mass_arr @ coords) / total_mass
        return r_com.astype(np.float64)
    else:
        batch_size = coords.shape[0]
        if mass_arr.ndim == 1:
            if mass_arr.shape[0] != n_atoms:
                raise ValueError(
                    f"Masses length ({mass_arr.shape[0]}) does not match number of atoms per batch ({n_atoms})."
                )
        elif mass_arr.ndim == 2:
            if mass_arr.shape == (batch_size, n_atoms):
                pass
            elif mass_arr.shape == (n_atoms, 1) or mass_arr.shape == (1, n_atoms):
                mass_arr = mass_arr.reshape(-1)
            else:
                raise ValueError(
                    f"For batched coordinates of shape {coords.shape}, masses must have shape ({n_atoms},) or ({batch_size}, {n_atoms}), got {mass_arr.shape}."
                )
        else:
            raise ValueError(
                f"For batched coordinates, masses must have 1 or 2 dimensions, got {mass_arr.ndim}D with shape {mass_arr.shape}."
            )

        if np.any(mass_arr <= 0.0):
            raise ValueError("All individual atomic masses must be strictly positive (> 0).")

        if mass_arr.ndim == 1:
            total_mass = float(np.sum(mass_arr))
            if total_mass <= 0.0:
                raise ValueError("Total molecular mass must be strictly positive (> 0).")
            r_com = (mass_arr @ coords) / total_mass
            return r_com.astype(np.float64)
        else:
            total_mass = np.sum(mass_arr, axis=1, keepdims=True)
            if np.any(total_mass <= 0.0):
                raise ValueError("Total molecular mass for each batch element must be strictly positive (> 0).")
            weighted_sum = np.einsum("bn,bnd->bd", mass_arr, coords)
            r_com = weighted_sum / total_mass
            return r_com.astype(np.float64)


# ============================================================================
# Coordinate Translation & Residual Verification (WBS 1.3.1.2 & 1.3.1.3)
# ============================================================================

def translate_to_center_of_mass(
    coordinates: np.ndarray,
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
    enforce_residual_gate: bool = True,
    tol: float = 1e-12,
) -> Tuple[np.ndarray, np.ndarray]:
    """Translate molecular coordinates to the mass-weighted center of mass.

    Computes R_COM and subtracts it from coordinates using vectorized broadcasting:
        r_tilde_i = r_i - R_COM

    Applies dual-pass compensated summation (WBS 1.3.1.2.2) when residual exceeds tolerance
    or under extreme coordinate regimes (|R| > 1e4 Angstroms), eliminating catastrophic
    cancellation to guarantee Invariant VR-01-T01 (delta_COM < 1e-12 u*Angstrom).

    Args:
        coordinates: Molecular coordinates of shape (N, 3) or (B, N, 3) in Angstroms.
        masses: Optional sequence or numpy array of atomic masses in unified atomic mass units (u).
        symbols: Optional sequence of IUPAC nuclide symbols.
        enforce_residual_gate: If True, evaluates verify_com_residual and raises
            COMResidualError if residual norm >= tol.
        tol: Invariant threshold tolerance in u*Angstrom (default: 1e-12).

    Returns:
        Tuple of (coordinates_centered, r_com), where:
            coordinates_centered has the identical shape and float64 dtype as coordinates,
            r_com has shape (3,) for unbatched or (B, 3) for batched geometries.

    Raises:
        COMResidualError: If enforce_residual_gate is True and residual >= tol.
        ValueError or TypeError: If inputs violate dimensional or physical preconditions.
    """
    if isinstance(coordinates, np.ndarray) and coordinates.dtype == np.float64:
        coords = coordinates
    else:
        if not isinstance(coordinates, (np.ndarray, list, tuple)):
            raise TypeError(
                f"Coordinates must be an array-like structure, got {type(coordinates).__name__}."
            )
        try:
            coords = np.asarray(coordinates, dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Coordinates could not be converted to float64 array: {exc}") from exc

    ndim = coords.ndim
    if ndim not in (2, 3):
        raise ValueError(
            f"Coordinates must have 2 or 3 dimensions: (N, 3) or (B, N, 3), got shape {coords.shape} ({ndim}D)."
        )
    if coords.shape[-1] != 3:
        raise ValueError(
            f"Last dimension of coordinates must be 3 (Cartesian x, y, z), got {coords.shape[-1]}."
        )
    n_atoms = coords.shape[-2]
    if n_atoms == 0:
        raise ValueError("Coordinate array must contain at least 1 atom (N >= 1).")
    if ndim == 3 and coords.shape[0] == 0:
        raise ValueError("Batch coordinate tensor must contain at least 1 structure (B >= 1).")
    if not np.isfinite(coords.sum()):
        raise ValueError("Coordinates must not contain NaN or Inf values.")

    # Resolve masses
    if masses is None:
        if symbols is None:
            raise ValueError("Either 'masses' or 'symbols' must be provided.")
        if isinstance(symbols, str):
            raise TypeError("Symbols must be a sequence of nuclide strings, not a single string.")
        if len(symbols) != n_atoms:
            raise ValueError(
                f"Number of chemical symbols ({len(symbols)}) does not match number of atoms ({n_atoms})."
            )
        resolved_masses = [disambiguate_mass(s) for s in symbols]
        mass_arr = np.asarray(resolved_masses, dtype=np.float64)
    else:
        if isinstance(masses, np.ndarray) and masses.dtype == np.float64:
            mass_arr = masses
        else:
            try:
                mass_arr = np.asarray(masses, dtype=np.float64)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Masses could not be converted to float64 array: {exc}") from exc

        if mass_arr.size == 0:
            raise ValueError("Masses array must not be empty.")

    tol_sq = tol * tol

    if ndim == 2:
        if mass_arr.ndim == 1:
            if mass_arr.shape[0] != n_atoms:
                raise ValueError(
                    f"Masses length ({mass_arr.shape[0]}) does not match number of atoms ({n_atoms})."
                )
        elif mass_arr.ndim == 2 and mass_arr.shape == (n_atoms, 1):
            mass_arr = mass_arr.reshape(-1)
        else:
            raise ValueError(
                f"For unbatched coordinates of shape {coords.shape}, masses must have shape ({n_atoms},), got {mass_arr.shape}."
            )

        total_mass = float(np.sum(mass_arr))
        if not np.isfinite(total_mass):
            raise ValueError("Masses must not contain NaN or Inf values.")
        if np.any(mass_arr <= 0.0):
            raise ValueError("All individual atomic masses must be strictly positive (> 0).")
        if total_mass <= 0.0:
            raise ValueError("Total molecular mass must be strictly positive (> 0).")

        r_com = (mass_arr @ coords) / total_mass
        centered = coords - r_com

        res_vec = mass_arr @ centered
        res_sq = float(res_vec[0] * res_vec[0] + res_vec[1] * res_vec[1] + res_vec[2] * res_vec[2])
        if res_sq >= tol_sq or abs(r_com[0]) > 1e4 or abs(r_com[1]) > 1e4 or abs(r_com[2]) > 1e4:
            delta_r = res_vec / total_mass
            centered -= delta_r
            r_com += delta_r
            res_vec = mass_arr @ centered
            res_sq = float(res_vec[0] * res_vec[0] + res_vec[1] * res_vec[1] + res_vec[2] * res_vec[2])

        if enforce_residual_gate and res_sq >= tol_sq:
            res_norm = float(np.sqrt(res_sq))
            raise COMResidualError(
                f"Center of mass residual norm {res_norm:.4e} u*Angstrom exceeds invariant tolerance {tol:.4e} u*Angstrom (VR-01-T01 breach)."
            )

        return centered, r_com.astype(np.float64)

    else:
        batch_size = coords.shape[0]
        if mass_arr.ndim == 1:
            if mass_arr.shape[0] != n_atoms:
                raise ValueError(
                    f"Masses length ({mass_arr.shape[0]}) does not match number of atoms per batch ({n_atoms})."
                )
        elif mass_arr.ndim == 2:
            if mass_arr.shape == (batch_size, n_atoms):
                pass
            elif mass_arr.shape == (n_atoms, 1) or mass_arr.shape == (1, n_atoms):
                mass_arr = mass_arr.reshape(-1)
            else:
                raise ValueError(
                    f"For batched coordinates of shape {coords.shape}, masses must have shape ({n_atoms},) or ({batch_size}, {n_atoms}), got {mass_arr.shape}."
                )
        else:
            raise ValueError(
                f"For batched coordinates, masses must have 1 or 2 dimensions, got {mass_arr.ndim}D with shape {mass_arr.shape}."
            )

        if np.any(mass_arr <= 0.0):
            raise ValueError("All individual atomic masses must be strictly positive (> 0).")

        if mass_arr.ndim == 1:
            total_mass = float(np.sum(mass_arr))
            if total_mass <= 0.0:
                raise ValueError("Total molecular mass must be strictly positive (> 0).")
            r_com = (mass_arr @ coords) / total_mass
            centered = coords - r_com[:, None, :]
            res_vecs = mass_arr @ centered
            norms_sq = np.sum(res_vecs * res_vecs, axis=1)
            if np.any(norms_sq >= tol_sq) or np.max(np.abs(r_com)) > 1e4:
                delta_r = res_vecs / total_mass
                centered -= delta_r[:, None, :]
                r_com += delta_r
                res_vecs = mass_arr @ centered
                norms_sq = np.sum(res_vecs * res_vecs, axis=1)
            max_res_sq = float(np.max(norms_sq))
        else:
            total_mass = np.sum(mass_arr, axis=1, keepdims=True)
            if np.any(total_mass <= 0.0):
                raise ValueError("Total molecular mass for each batch element must be strictly positive (> 0).")
            weighted_sum = np.einsum("bn,bnd->bd", mass_arr, coords)
            r_com = weighted_sum / total_mass
            centered = coords - r_com[:, None, :]
            res_vecs = np.einsum("bn,bnd->bd", mass_arr, centered)
            norms_sq = np.sum(res_vecs * res_vecs, axis=1)
            if np.any(norms_sq >= tol_sq) or np.max(np.abs(r_com)) > 1e4:
                delta_r = res_vecs / total_mass
                centered -= delta_r[:, None, :]
                r_com += delta_r
                res_vecs = np.einsum("bn,bnd->bd", mass_arr, centered)
                norms_sq = np.sum(res_vecs * res_vecs, axis=1)
            max_res_sq = float(np.max(norms_sq))

        if enforce_residual_gate and max_res_sq >= tol_sq:
            max_res = float(np.sqrt(max_res_sq))
            raise COMResidualError(
                f"Maximum batch center of mass residual norm {max_res:.4e} u*Angstrom exceeds invariant tolerance {tol:.4e} u*Angstrom (VR-01-T01 breach)."
            )

        return centered, r_com.astype(np.float64)


def verify_com_residual(
    coordinates_centered: np.ndarray,
    masses: np.ndarray,
    tol: float = 1e-12,
) -> float:
    """Verify that mass-weighted center of mass residual norm satisfies Invariant VR-01-T01.

    Mathematical residual:
        delta_COM = || sum_{i=1}^N m_i * r_tilde_i ||_2 < tol

    Args:
        coordinates_centered: Centered molecular coordinates (N, 3) or (B, N, 3).
        masses: Atomic masses array of shape (N,) or (B, N).
        tol: Invariant threshold tolerance in u * Angstrom (default: 1e-12).

    Returns:
        Residual norm (or maximum residual across batch) as float.

    Raises:
        COMResidualError: If residual norm >= tol.
        ValueError: If input dimensions are invalid or contain NaN/Inf.
    """
    if isinstance(coordinates_centered, np.ndarray) and coordinates_centered.dtype == np.float64:
        coords = coordinates_centered
    else:
        coords = np.asarray(coordinates_centered, dtype=np.float64)

    if isinstance(masses, np.ndarray) and masses.dtype == np.float64:
        m_arr = masses
    else:
        m_arr = np.asarray(masses, dtype=np.float64)

    if not np.isfinite(coords.sum()):
        raise ValueError("Centered coordinates must not contain NaN or Inf values.")
    if not np.isfinite(m_arr.sum()):
        raise ValueError("Masses must not contain NaN or Inf values.")
    if np.any(m_arr <= 0.0):
        raise ValueError("All individual atomic masses must be strictly positive (> 0).")

    if coords.ndim == 2:
        if m_arr.ndim == 2 and m_arr.shape == (coords.shape[0], 1):
            m_arr = m_arr.reshape(-1)
        if m_arr.ndim != 1 or m_arr.shape[0] != coords.shape[0]:
            raise ValueError(
                f"Masses shape {m_arr.shape} does not match coords shape {coords.shape}."
            )
        residual_vec = m_arr @ coords  # shape (3,)
        residual_norm = float(np.linalg.norm(residual_vec))
        if residual_norm >= tol:
            raise COMResidualError(
                f"Center of mass residual norm {residual_norm:.4e} u*Angstrom exceeds invariant tolerance {tol:.4e} u*Angstrom (VR-01-T01 breach)."
            )
        return residual_norm

    elif coords.ndim == 3:
        b_size, n_atoms, _ = coords.shape
        if m_arr.ndim == 1:
            if m_arr.shape[0] != n_atoms:
                raise ValueError(
                    f"Masses shape {m_arr.shape} does not match coords shape {coords.shape}."
                )
            residual_vecs = m_arr @ coords  # shape (B, 3)
        elif m_arr.ndim == 2:
            if m_arr.shape == (n_atoms, 1) or m_arr.shape == (1, n_atoms):
                m_arr = m_arr.reshape(-1)
                residual_vecs = m_arr @ coords
            elif m_arr.shape == (b_size, n_atoms):
                residual_vecs = np.einsum("bn,bnd->bd", m_arr, coords)  # shape (B, 3)
            else:
                raise ValueError(
                    f"Masses shape {m_arr.shape} does not match coords shape {coords.shape}."
                )
        else:
            raise ValueError(
                f"Unexpected masses shape {m_arr.shape} for 3D coordinates."
            )

        norms = np.linalg.norm(residual_vecs, axis=1)  # shape (B,)
        max_residual = float(np.max(norms))
        if max_residual >= tol:
            raise COMResidualError(
                f"Maximum batch center of mass residual norm {max_residual:.4e} u*Angstrom exceeds invariant tolerance {tol:.4e} u*Angstrom (VR-01-T01 breach)."
            )
        return max_residual

    else:
        raise ValueError(
            f"Coordinates must have 2 or 3 dimensions: (N, 3) or (B, N, 3), got shape {coords.shape}."
        )


# ============================================================================
# Mass-Weighted Covariance (Gram) Matrix Formulation (WBS 1.4.1)
# ============================================================================

def compute_mass_weighted_covariance_matrix(
    coords_ref: np.ndarray,
    coords_target: np.ndarray,
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
    center: bool = True,
    tol: float = 1e-12,
) -> np.ndarray:
    """Compute the mass-weighted covariance (Gram) matrix between reference and target geometries.

    Mathematical formulation (WBS 1.4.1.1):
        C = R_tilde_ref^T * M * R_tilde_target
          = sum_{i=1}^N m_i * r_tilde_i,ref * (r_tilde_i,target)^T

    where:
        - R_tilde_ref and R_tilde_target are centered coordinates (origin at mass-weighted COM).
        - M = diag(m_1, ..., m_N) is the diagonal mass-weighting tensor.
        - C is a 3x3 real matrix (or (B, 3, 3) for batched inputs).

    Supports unbatched coordinates (N, 3), batched coordinates (B, N, 3), and broadcasting
    where coords_ref is (N, 3) and coords_target is (B, N, 3) (or vice versa).

    Args:
        coords_ref: Reference molecular coordinates of shape (N, 3) or (B, N, 3).
        coords_target: Target molecular coordinates of shape (N, 3) or (B, N, 3).
        masses: Optional atomic masses in unified atomic mass units (u).
            Shape (N,) for unbatched or (B, N) / (N,) for batched.
        symbols: Optional sequence of IUPAC nuclide symbols (e.g. ['O', 'H', 'H']).
            Required if masses is None, dynamically resolved via Mendeleev.
        center: If True (default), translates both reference and target coordinates to
            their respective mass-weighted centers of mass via translate_to_center_of_mass().
            If False, assumes coordinates are already centered.
        tol: Invariant threshold tolerance for COM translation in u * Angstrom (default: 1e-12).

    Returns:
        np.ndarray: Mass-weighted covariance matrix of shape (3, 3) for unbatched inputs,
            or (B, 3, 3) for batched inputs, with float64 dtype.

    Raises:
        TypeError: If coordinates are not array-like or symbols have invalid types.
        ValueError: If dimensions mismatch, coordinate last dimension is not 3,
            arrays contain NaN or Inf values, or atomic masses are non-positive.
    """
    # 1. Type validation and conversion
    if isinstance(coords_ref, np.ndarray) and coords_ref.dtype == np.float64:
        ref = coords_ref
    else:
        if not isinstance(coords_ref, (np.ndarray, list, tuple)):
            raise TypeError(
                f"coords_ref must be an array-like structure, got {type(coords_ref).__name__}."
            )
        try:
            ref = np.asarray(coords_ref, dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"coords_ref could not be converted to float64 array: {exc}") from exc

    if isinstance(coords_target, np.ndarray) and coords_target.dtype == np.float64:
        target = coords_target
    else:
        if not isinstance(coords_target, (np.ndarray, list, tuple)):
            raise TypeError(
                f"coords_target must be an array-like structure, got {type(coords_target).__name__}."
            )
        try:
            target = np.asarray(coords_target, dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"coords_target could not be converted to float64 array: {exc}") from exc

    # 2. Finiteness checks
    if not np.isfinite(ref.sum()):
        raise ValueError("coords_ref must not contain NaN or Inf values.")
    if not np.isfinite(target.sum()):
        raise ValueError("coords_target must not contain NaN or Inf values.")

    # 3. Dimensionality validation
    if ref.ndim not in (2, 3):
        raise ValueError(
            f"coords_ref must have 2 or 3 dimensions: (N, 3) or (B, N, 3), got shape {ref.shape} ({ref.ndim}D)."
        )
    if target.ndim not in (2, 3):
        raise ValueError(
            f"coords_target must have 2 or 3 dimensions: (N, 3) or (B, N, 3), got shape {target.shape} ({target.ndim}D)."
        )
    if ref.shape[-1] != 3:
        raise ValueError(f"Last dimension of coords_ref must be 3, got {ref.shape[-1]}.")
    if target.shape[-1] != 3:
        raise ValueError(f"Last dimension of coords_target must be 3, got {target.shape[-1]}.")

    n_atoms_ref = ref.shape[-2]
    n_atoms_target = target.shape[-2]
    if n_atoms_ref == 0:
        raise ValueError("coords_ref must contain at least 1 atom (N >= 1).")
    if n_atoms_ref != n_atoms_target:
        raise ValueError(
            f"Atom count mismatch: coords_ref has {n_atoms_ref} atoms, coords_target has {n_atoms_target} atoms."
        )
    n_atoms = n_atoms_ref

    # 4. Batch alignment and broadcasting
    is_batched = (ref.ndim == 3 or target.ndim == 3)
    if is_batched:
        if ref.ndim == 2 and target.ndim == 3:
            batch_size = target.shape[0]
            if batch_size == 0:
                raise ValueError("Batch coordinate tensor must contain at least 1 structure (B >= 1).")
            ref_expanded = np.broadcast_to(ref, (batch_size, n_atoms, 3))
            target_expanded = target
        elif ref.ndim == 3 and target.ndim == 2:
            batch_size = ref.shape[0]
            if batch_size == 0:
                raise ValueError("Batch coordinate tensor must contain at least 1 structure (B >= 1).")
            ref_expanded = ref
            target_expanded = np.broadcast_to(target, (batch_size, n_atoms, 3))
        else:
            if ref.shape[0] != target.shape[0]:
                raise ValueError(
                    f"Batch size mismatch: coords_ref has {ref.shape[0]}, coords_target has {target.shape[0]}."
                )
            batch_size = ref.shape[0]
            if batch_size == 0:
                raise ValueError("Batch coordinate tensor must contain at least 1 structure (B >= 1).")
            ref_expanded = ref
            target_expanded = target
    else:
        ref_expanded = ref
        target_expanded = target

    # 5. Mass resolution
    if masses is None:
        if symbols is None:
            raise ValueError("Either 'masses' or 'symbols' must be provided to compute covariance matrix.")
        if isinstance(symbols, str):
            raise TypeError("Symbols must be a sequence of nuclide strings, not a single string.")
        if len(symbols) != n_atoms:
            raise ValueError(
                f"Number of chemical symbols ({len(symbols)}) does not match number of atoms ({n_atoms})."
            )
        resolved_masses = [disambiguate_mass(s) for s in symbols]
        mass_arr = np.asarray(resolved_masses, dtype=np.float64)
    else:
        if isinstance(masses, np.ndarray) and masses.dtype == np.float64:
            mass_arr = masses
        else:
            try:
                mass_arr = np.asarray(masses, dtype=np.float64)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Masses could not be converted to float64 array: {exc}") from exc

        if mass_arr.size == 0:
            raise ValueError("Masses array must not be empty.")
        if not np.isfinite(mass_arr.sum()):
            raise ValueError("Masses must not contain NaN or Inf values.")

    if np.any(mass_arr <= 0.0):
        raise ValueError("All individual atomic masses must be strictly positive (> 0).")

    # Validate mass array shape
    if not is_batched:
        if mass_arr.ndim == 1:
            if mass_arr.shape[0] != n_atoms:
                raise ValueError(
                    f"Masses length ({mass_arr.shape[0]}) does not match number of atoms ({n_atoms})."
                )
        elif mass_arr.ndim == 2 and mass_arr.shape == (n_atoms, 1):
            mass_arr = mass_arr.reshape(-1)
        else:
            raise ValueError(
                f"For unbatched coordinates, masses must have shape ({n_atoms},), got {mass_arr.shape}."
            )
    else:
        if mass_arr.ndim == 1:
            if mass_arr.shape[0] != n_atoms:
                raise ValueError(
                    f"Masses length ({mass_arr.shape[0]}) does not match number of atoms ({n_atoms})."
                )
        elif mass_arr.ndim == 2:
            if mass_arr.shape == (batch_size, n_atoms):
                pass
            elif mass_arr.shape == (n_atoms, 1) or mass_arr.shape == (1, n_atoms):
                mass_arr = mass_arr.reshape(-1)
            else:
                raise ValueError(
                    f"For batched coordinates, masses must have shape ({n_atoms},) or ({batch_size}, {n_atoms}), got {mass_arr.shape}."
                )
        else:
            raise ValueError(
                f"Unexpected masses shape {mass_arr.shape} for 3D coordinates."
            )

    # 6. Centering coordinates if requested
    if center:
        ref_centered, _ = translate_to_center_of_mass(
            ref_expanded, masses=mass_arr, enforce_residual_gate=True, tol=tol
        )
        target_centered, _ = translate_to_center_of_mass(
            target_expanded, masses=mass_arr, enforce_residual_gate=True, tol=tol
        )
    else:
        ref_centered = ref_expanded
        target_centered = target_expanded

    # 7. Mass-weighted covariance accumulation
    if not is_batched:
        # C = R_ref^T * (M * R_target) -> shape (3, 3)
        c_mat = ref_centered.T @ (mass_arr[:, None] * target_centered)
        return c_mat.astype(np.float64)
    else:
        # Batched einsum -> shape (B, 3, 3)
        if mass_arr.ndim == 1:
            c_mat = np.einsum(
                "bni,n,bnj->bij", ref_centered, mass_arr, target_centered, optimize=True
            )
        else:
            c_mat = np.einsum(
                "bni,bn,bnj->bij", ref_centered, mass_arr, target_centered, optimize=True
            )
        return c_mat.astype(np.float64)


def compute_covariance_frobenius_norm(
    covariance_matrix: np.ndarray,
) -> Union[float, np.ndarray]:
    """Compute the Frobenius norm ||C||_F of the covariance matrix.

    Mathematical formulation (WBS 1.4.1.2):
        ||C||_F = sqrt( sum_{j=1}^3 sum_{k=1}^3 C_{jk}^2 ) = sqrt( Tr(C^T C) )

    Args:
        covariance_matrix: Covariance matrix of shape (3, 3) or batched (B, 3, 3).

    Returns:
        float for unbatched (3, 3) input, or np.ndarray of shape (B,) for batched (B, 3, 3).

    Raises:
        ValueError: If dimensions are invalid or matrix contains NaN/Inf.
    """
    if isinstance(covariance_matrix, np.ndarray) and covariance_matrix.dtype == np.float64:
        c_mat = covariance_matrix
    else:
        try:
            c_mat = np.asarray(covariance_matrix, dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"covariance_matrix could not be converted to float64 array: {exc}") from exc

    if c_mat.ndim not in (2, 3) or c_mat.shape[-2:] != (3, 3):
        raise ValueError(
            f"covariance_matrix must have shape (3, 3) or (B, 3, 3), got shape {c_mat.shape}."
        )
    if not np.isfinite(c_mat.sum()):
        raise ValueError("covariance_matrix must not contain NaN or Inf values.")

    norm = np.linalg.norm(c_mat, ord="fro", axis=(-2, -1))
    if c_mat.ndim == 2:
        return float(norm)
    return norm.astype(np.float64)


def check_covariance_symmetry(
    covariance_matrix: np.ndarray,
    tol: float = 1e-12,
) -> Union[bool, np.ndarray]:
    """Verify matrix symmetry condition ||C - C^T||_F < tol (WBS 1.4.1.2).

    For identical conformations (R_ref == R_target), the covariance matrix C is symmetric
    and represents the mass-weighted moment tensor (Gram matrix).

    Args:
        covariance_matrix: Covariance matrix of shape (3, 3) or batched (B, 3, 3).
        tol: Symmetry tolerance under Frobenius norm (default: 1e-12).

    Returns:
        bool for unbatched (3, 3) input, or np.ndarray of booleans of shape (B,) for batched.

    Raises:
        ValueError: If input dimensions are invalid or contain NaN/Inf.
    """
    if isinstance(covariance_matrix, np.ndarray) and covariance_matrix.dtype == np.float64:
        c_mat = covariance_matrix
    else:
        try:
            c_mat = np.asarray(covariance_matrix, dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"covariance_matrix could not be converted to float64 array: {exc}") from exc

    if c_mat.ndim not in (2, 3) or c_mat.shape[-2:] != (3, 3):
        raise ValueError(
            f"covariance_matrix must have shape (3, 3) or (B, 3, 3), got shape {c_mat.shape}."
        )
    if not np.isfinite(c_mat.sum()):
        raise ValueError("covariance_matrix must not contain NaN or Inf values.")

    diff = c_mat - np.swapaxes(c_mat, -2, -1)
    asym_norm = np.linalg.norm(diff, ord="fro", axis=(-2, -1))
    if c_mat.ndim == 2:
        return bool(float(asym_norm) < tol)
    return (asym_norm < tol)


# ============================================================================
# SVD Factorization & Reflection Parity Inversion Gate (WBS 1.4.2)
# ============================================================================

def compute_svd_rotation_matrix(
    covariance_matrix: np.ndarray,
    enforce_so3: bool = True,
    tol_degeneracy: float = 1e-8,
) -> np.ndarray:
    """Compute optimal proper rotation matrix U via SVD and reflection parity gate (S_det).

    Mathematical formulation (WBS 1.4.2.1 - 1.4.2.4):
        C = V Sigma W^T
        d = det(V W^T)
        S_det = diag(1, 1, d)
        U = V S_det W^T

    Invariant VR-01-R01: Proper rotation group closure det(U) = +1.0 strictly enforced.
    Preserves stereochemical parity when presented with enantiomeric structures.

    Args:
        covariance_matrix: Covariance matrix of shape (3, 3) or batched (B, 3, 3).
        enforce_so3: If True, asserts Invariant VR-01-R01 (|det(U) - 1.0| < 1e-12).
        tol_degeneracy: Threshold for detecting collinear (sigma_2 < tol) or planar (sigma_3 < tol) degeneracy.

    Returns:
        np.ndarray: Proper rotation matrix U in SO(3) of shape (3, 3) or (B, 3, 3), float64.

    Raises:
        SO3ClosureError: If proper rotation group closure is violated.
        ValueError: If inputs have invalid dimensions or non-finite values.
    """
    if isinstance(covariance_matrix, np.ndarray) and covariance_matrix.dtype == np.float64:
        c_mat = covariance_matrix
    else:
        try:
            c_mat = np.asarray(covariance_matrix, dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"covariance_matrix could not be converted to float64 array: {exc}") from exc

    if c_mat.ndim not in (2, 3) or c_mat.shape[-2:] != (3, 3):
        raise ValueError(
            f"covariance_matrix must have shape (3, 3) or (B, 3, 3), got shape {c_mat.shape}."
        )
    if not np.isfinite(c_mat.sum()):
        raise ValueError("covariance_matrix must not contain NaN or Inf values.")

    is_unbatched = (c_mat.ndim == 2)
    if is_unbatched:
        v_mat, s_vals, wt_mat = np.linalg.svd(c_mat)
        det_prod = float(np.linalg.det(v_mat @ wt_mat))
        d_val = 1.0 if det_prod >= 0.0 else -1.0
        s_det = np.diag([1.0, 1.0, d_val])
        u_mat = v_mat @ s_det @ wt_mat

        if enforce_so3:
            verify_so3_closure(u_mat)

        return u_mat.astype(np.float64)
    else:
        v_mat, s_vals, wt_mat = np.linalg.svd(c_mat)  # (B, 3, 3)
        prod = v_mat @ wt_mat
        det_prods = np.linalg.det(prod)  # (B,)
        b_size = c_mat.shape[0]
        s_det = np.zeros((b_size, 3, 3), dtype=np.float64)
        s_det[:, 0, 0] = 1.0
        s_det[:, 1, 1] = 1.0
        s_det[:, 2, 2] = np.where(det_prods >= 0.0, 1.0, -1.0)
        u_mat = v_mat @ s_det @ wt_mat

        if enforce_so3:
            verify_so3_closure(u_mat)

        return u_mat.astype(np.float64)


# ============================================================================
# Proper Rotation Group SO(3) Closure (WBS 1.4.3)
# ============================================================================

def verify_so3_closure(
    rotation_matrix: np.ndarray,
    tol: float = 1e-12,
) -> bool:
    """Assert Invariant VR-01-R01: Proper rotation group SO(3) closure.

    Verifies:
        1. Orthogonality: ||U^T U - I_3||_F < tol
        2. Proper orientation: |det(U) - 1.0| < tol

    Args:
        rotation_matrix: Rotation matrix of shape (3, 3) or (B, 3, 3).
        tol: Tolerance threshold (default: 1e-12).

    Returns:
        bool: True if all invariants are satisfied.

    Raises:
        SO3ClosureError: If orthogonality or determinant condition is breached.
    """
    if not isinstance(rotation_matrix, np.ndarray):
        r_mat = np.asarray(rotation_matrix, dtype=np.float64)
    else:
        r_mat = rotation_matrix

    if r_mat.ndim not in (2, 3) or r_mat.shape[-2:] != (3, 3):
        raise ValueError(f"rotation_matrix must have shape (3, 3) or (B, 3, 3), got {r_mat.shape}.")
    if not np.isfinite(r_mat.sum()):
        raise ValueError("rotation_matrix contains non-finite values (NaN or Inf).")

    eye = np.eye(3, dtype=np.float64)
    if r_mat.ndim == 2:
        ortho_err = float(np.linalg.norm(r_mat.T @ r_mat - eye, ord="fro"))
        if ortho_err >= tol:
            raise SO3ClosureError(
                f"Orthogonality breach: ||U^T U - I||_F = {ortho_err:.3e} >= {tol:.3e}."
            )
        det_val = float(np.linalg.det(r_mat))
        if abs(det_val - 1.0) >= tol:
            raise SO3ClosureError(
                f"SO(3) determinant breach: det(U) = {det_val:.12f} != +1.0 (|det - 1| = {abs(det_val - 1.0):.3e} >= {tol:.3e})."
            )
        return True
    else:
        prod = np.swapaxes(r_mat, -2, -1) @ r_mat
        ortho_errs = np.linalg.norm(prod - eye, ord="fro", axis=(-2, -1))
        max_ortho_err = float(np.max(ortho_errs))
        if max_ortho_err >= tol:
            raise SO3ClosureError(
                f"Maximum batched orthogonality breach: ||U^T U - I||_F = {max_ortho_err:.3e} >= {tol:.3e}."
            )
        dets = np.linalg.det(r_mat)
        max_det_err = float(np.max(np.abs(dets - 1.0)))
        if max_det_err >= tol:
            raise SO3ClosureError(
                f"Maximum batched SO(3) determinant breach: |det(U) - 1.0| = {max_det_err:.3e} >= {tol:.3e}."
            )
        return True


# ============================================================================
# Eckart Angular Momentum Cross-Product Residual Gate (WBS 1.4.4)
# ============================================================================

def compute_eckart_angular_momentum_residual(
    coords_ref: np.ndarray,
    coords_aligned: np.ndarray,
    masses: np.ndarray,
) -> Tuple[np.ndarray, Union[float, np.ndarray]]:
    """Compute the Eckart angular momentum cross-product residual vector (WBS 1.4.4.1 - 1.4.4.2).

    Mathematical formulation:
        L_Eckart = sum_{i=1}^N m_i * (r_tilde_{i, ref} x r_{i, aligned})
        delta_Eckart = ||L_Eckart||_2

    Args:
        coords_ref: Centered reference coordinates of shape (N, 3) or (B, N, 3).
        coords_aligned: Centered and rotated target coordinates of shape (N, 3) or (B, N, 3).
        masses: Atomic masses array of shape (N,) or (B, N).

    Returns:
        Tuple of (L_Eckart, delta_Eckart):
            L_Eckart: residual vector of shape (3,) or (B, 3).
            delta_Eckart: Euclidean norm as float or np.ndarray of shape (B,).
    """
    ref = np.asarray(coords_ref, dtype=np.float64)
    target = np.asarray(coords_aligned, dtype=np.float64)
    m_arr = np.asarray(masses, dtype=np.float64)

    if ref.ndim == 2:
        cross_prod = np.cross(ref, target)  # (N, 3)
        if m_arr.ndim == 2 and m_arr.shape == (ref.shape[0], 1):
            m_arr = m_arr.reshape(-1)
        l_vec = np.sum(m_arr[:, None] * cross_prod, axis=0)  # (3,)
        norm_val = float(np.linalg.norm(l_vec))
        return l_vec, norm_val
    else:
        cross_prod = np.cross(ref, target)  # (B, N, 3)
        if m_arr.ndim == 1:
            l_vec = np.einsum("n,bnd->bd", m_arr, cross_prod)  # (B, 3)
        else:
            l_vec = np.einsum("bn,bnd->bd", m_arr, cross_prod)  # (B, 3)
        norm_vals = np.linalg.norm(l_vec, axis=1)  # (B,)
        return l_vec, norm_vals


def verify_eckart_residual(
    coords_ref: np.ndarray,
    coords_aligned: np.ndarray,
    masses: np.ndarray,
    tol: float = 1e-10,
) -> float:
    """Assert Invariant VR-01-R02: delta_Eckart < 1e-10 u * Angstrom^2 (WBS 1.4.4.3).

    Args:
        coords_ref: Centered reference coordinates.
        coords_aligned: Centered and aligned target coordinates.
        masses: Atomic masses array.
        tol: Invariant threshold tolerance in u * Angstrom^2 (default: 1e-10).

    Returns:
        float: Evaluated Eckart residual norm (or max across batch).

    Raises:
        EckartResidualError: If delta_Eckart >= tol.
    """
    _, norm_val = compute_eckart_angular_momentum_residual(coords_ref, coords_aligned, masses)
    if isinstance(norm_val, (float, int)):
        res_float = float(norm_val)
        if res_float >= tol:
            raise EckartResidualError(
                f"Eckart residual {res_float:.3e} exceeds invariant threshold {tol:.3e} (VR-01-R02 breach)."
            )
        return res_float
    else:
        max_res = float(np.max(norm_val))
        if max_res >= tol:
            raise EckartResidualError(
                f"Maximum batched Eckart residual {max_res:.3e} exceeds invariant threshold {tol:.3e} (VR-01-R02 breach)."
            )
        return max_res


# ============================================================================
# Collinear & Planar Degeneracy Resolution Engine (WBS 1.4.5)
# ============================================================================

def resolve_collinear_planar_degeneracy(
    c_mat: np.ndarray,
    tol_degeneracy: float = 1e-8,
) -> Tuple[np.ndarray, str]:
    """Detect and resolve rank deficiency for collinear and planar molecular systems (WBS 1.4.5).

    Detects:
        - Collinear rotor (sigma_2 < tol_degeneracy): Gram-Schmidt nullspace completion about internuclear axis.
        - Planar system (sigma_3 < tol_degeneracy): Preserves sign of out-of-plane normal vector n = v_1 x v_2.

    Args:
        c_mat: 3x3 covariance matrix.
        tol_degeneracy: Singular value threshold (default: 1e-8).

    Returns:
        Tuple of (proper rotation matrix U in SO(3), system_geometry_classification).
    """
    v_mat, s_vals, wt_mat = np.linalg.svd(c_mat)

    if s_vals[1] < tol_degeneracy:
        classification = "COLLINEAR"
        v1 = v_mat[:, 0]
        w1 = wt_mat[0, :]

        # Gram-Schmidt completion for v
        arb = np.array([1.0, 0.0, 0.0]) if abs(v1[0]) < 0.8 else np.array([0.0, 1.0, 0.0])
        v2 = arb - np.dot(arb, v1) * v1
        v2 /= np.linalg.norm(v2)
        v3 = np.cross(v1, v2)
        v_ortho = np.column_stack([v1, v2, v3])

        # Gram-Schmidt completion for w
        arb_w = np.array([1.0, 0.0, 0.0]) if abs(w1[0]) < 0.8 else np.array([0.0, 1.0, 0.0])
        w2 = arb_w - np.dot(arb_w, w1) * w1
        w2 /= np.linalg.norm(w2)
        w3 = np.cross(w1, w2)
        w_ortho = np.column_stack([w1, w2, w3])

        u_mat = v_ortho @ w_ortho.T
    elif s_vals[2] < tol_degeneracy:
        classification = "PLANAR"
        d = float(np.linalg.det(v_mat @ wt_mat))
        d_val = 1.0 if d >= 0.0 else -1.0
        s_det = np.diag([1.0, 1.0, d_val])
        u_mat = v_mat @ s_det @ wt_mat
    else:
        classification = "NON_PLANAR_3D"
        d = float(np.linalg.det(v_mat @ wt_mat))
        d_val = 1.0 if d >= 0.0 else -1.0
        s_det = np.diag([1.0, 1.0, d_val])
        u_mat = v_mat @ s_det @ wt_mat

    verify_so3_closure(u_mat)
    return u_mat, classification


# ============================================================================
# End-to-End Alignment & EckartFrameAligner Class (WBS 1.4.1 - 1.4.5)
# ============================================================================

def align_coordinates(
    coords_ref: np.ndarray,
    coords_target: np.ndarray,
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
    enforce_eckart_gate: bool = True,
    tol_eckart: float = 1e-10,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Align target coordinates to reference coordinates in the mass-weighted Eckart frame.

    Executes:
        1. COM translation of both reference and target geometries.
        2. Mass-weighted covariance matrix formulation C = R_ref^T M R_target.
        3. Proper rotation matrix computation U in SO(3) via SVD and reflection parity gate S_det.
        4. Coordinate rotation R_aligned = (U R_target^T)^T.
        5. Eckart angular momentum residual verification ||L_Eckart|| < tol_eckart.
        6. Mass-weighted RMSD evaluation.

    Args:
        coords_ref: Reference coordinates of shape (N, 3).
        coords_target: Target coordinates of shape (N, 3).
        masses: Optional atomic masses sequence or array.
        symbols: Optional IUPAC nuclide symbols sequence.
        enforce_eckart_gate: If True, asserts Invariant VR-01-R02.
        tol_eckart: Residual threshold in u * Angstrom^2 (default: 1e-10).

    Returns:
        Tuple of (coords_aligned, U_matrix, mass_weighted_rmsd):
            coords_aligned: Aligned coordinates of shape (N, 3).
            U_matrix: 3x3 proper rotation matrix in SO(3).
            mass_weighted_rmsd: Root-mean-square deviation in Angstroms.
    """
    ref_c, _ = translate_to_center_of_mass(coords_ref, masses=masses, symbols=symbols)
    target_c, _ = translate_to_center_of_mass(coords_target, masses=masses, symbols=symbols)

    if masses is None:
        if symbols is None:
            raise ValueError("Either masses or symbols must be provided.")
        mass_arr = np.asarray([disambiguate_mass(s) for s in symbols], dtype=np.float64)
    else:
        mass_arr = np.asarray(masses, dtype=np.float64)

    c_mat = compute_mass_weighted_covariance_matrix(ref_c, target_c, masses=mass_arr, center=False)
    u_mat = compute_svd_rotation_matrix(c_mat, enforce_so3=True)

    aligned = (u_mat @ target_c.T).T

    if enforce_eckart_gate:
        verify_eckart_residual(ref_c, aligned, mass_arr, tol=tol_eckart)

    total_mass = float(np.sum(mass_arr))
    sq_diff = np.sum((ref_c - aligned) ** 2, axis=1)
    rmsd = float(np.sqrt(np.sum(mass_arr * sq_diff) / total_mass))

    return aligned, u_mat, rmsd


class EckartFrameAligner:
    """Production Mass-Weighted Eckart Frame Alignment & SO(3) Closure Engine (Subsystem VR01-SS3)."""

    def __init__(self, tol_so3: float = 1e-12, tol_eckart: float = 1e-10) -> None:
        self.tol_so3 = tol_so3
        self.tol_eckart = tol_eckart

    def align(
        self,
        coords_ref: np.ndarray,
        coords_target: np.ndarray,
        masses: Optional[Union[Sequence[float], np.ndarray]] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """Align coords_target onto coords_ref in the Eckart frame."""
        return align_coordinates(
            coords_ref=coords_ref,
            coords_target=coords_target,
            masses=masses,
            symbols=symbols,
            enforce_eckart_gate=True,
            tol_eckart=self.tol_eckart,
        )

    def compute_covariance(
        self,
        coords_ref: np.ndarray,
        coords_target: np.ndarray,
        masses: Optional[Union[Sequence[float], np.ndarray]] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> np.ndarray:
        """Compute mass-weighted covariance matrix C."""
        return compute_mass_weighted_covariance_matrix(
            coords_ref=coords_ref,
            coords_target=coords_target,
            masses=masses,
            symbols=symbols,
        )

    def compute_rotation_matrix(self, covariance_matrix: np.ndarray) -> np.ndarray:
        """Compute proper rotation matrix U via SVD and reflection parity gate."""
        return compute_svd_rotation_matrix(covariance_matrix, enforce_so3=True)

