import jax
import jax.numpy as jnp

@jax.jit
def apply_flat_bottom_harmonic_confiner(
    coords_jax: jnp.ndarray,
    vdw_radii_jax: jnp.ndarray,
    k: float = 10.0,
    scaling: float = 2.5
) -> jnp.ndarray:
    """
    Computes a flat-bottom harmonic confining potential for a set of coordinates.
    
    Args:
        coords_jax: (N, 3) array of atomic coordinates.
        vdw_radii_jax: (N,) array of van der Waals radii.
        k: Force constant for the harmonic confiner.
        scaling: Scaling factor for the sum of van der Waals radii.
        
    Returns:
        The scalar potential energy.
    """
    # Pairwise differences
    diffs = coords_jax[:, None, :] - coords_jax[None, :, :]
    dists_sq = jnp.sum(diffs**2, axis=-1)
    
    # Safe distance calculation to avoid NaN gradients at 0 (e.g., self-interactions)
    safe_dists = jnp.sqrt(jnp.where(dists_sq > 1e-14, dists_sq, 1.0))
    # For the diagonal, dists_sq is 0, so safe_dists will be 1.0. 
    # But we will use jnp.where to explicitly mask out elements that aren't greater than r_cutoff anyway.
    
    # Actual distances (with 0 on diagonal, though gradient there would be NaN if we differentiated directly, 
    # but we will only use distances where dists_sq > 1e-14)
    dists = jnp.where(dists_sq > 1e-14, safe_dists, 0.0)
    
    # Cutoff distances
    r_cutoff = scaling * (vdw_radii_jax[:, None] + vdw_radii_jax[None, :])
    
    # Penalty calculation
    # We only penalize if dists > r_cutoff. 
    # Use jnp.where to ensure we don't differentiate the distance when it's 0.
    penalty = jnp.where(
        dists > r_cutoff,
        k * (dists - r_cutoff)**2,
        0.0
    )
    
    # Upper triangle sum to avoid double counting
    upper_tri_indices = jnp.triu_indices_from(penalty, k=1)
    energy = jnp.sum(penalty[upper_tri_indices])
    
    return energy
