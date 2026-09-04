import logging

logger = logging.getLogger("cochem.kie_profiler")

import h5py
import jax
import jax.numpy as jnp
import numpy as np
from qcelemental import periodictable as pt

try:
    import molsym
except ImportError:
    molsym = None

from collections.abc import Mapping
try:
    from mendeleev import element as _mendeleev_element
except ImportError:
    _mendeleev_element = None

_TARGET_HEAVY_MASS_NUMBERS = {
    "H": 2,    # Deuterium
    "C": 13,   # 13C
    "N": 15,   # 15N
    "O": 18,   # 18O
    "S": 34,   # 34S
    "Cl": 37,  # 37Cl
    "Br": 81,  # 81Br
}


class _DynamicHeavyIsotopesMap(Mapping):
    """Dynamic heavy isotope mass mapping backed by Mendeleev library."""

    def __getitem__(self, key: str) -> float:
        if not key or not isinstance(key, str):
            raise KeyError(key)
        sym = key.strip().capitalize()
        if sym not in _TARGET_HEAVY_MASS_NUMBERS:
            raise KeyError(key)

        mass_num = _TARGET_HEAVY_MASS_NUMBERS[sym]
        if _mendeleev_element is not None:
            try:
                el = _mendeleev_element(sym)
                for iso in getattr(el, "isotopes", []):
                    if iso.mass_number == mass_num and iso.mass is not None:
                        return float(iso.mass)
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

        # Fallback values if mendeleev is unavailable
        fallbacks = {
            "H": 2.014101778,
            "C": 13.003354835,
            "N": 15.000108898,
            "O": 17.999159612,
            "S": 33.96786690,
            "Cl": 36.96590260,
            "Br": 80.9162906,
        }
        return fallbacks[sym]

    def __iter__(self):
        return iter(_TARGET_HEAVY_MASS_NUMBERS.keys())

    def __len__(self):
        return len(_TARGET_HEAVY_MASS_NUMBERS)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key.strip().capitalize() in _TARGET_HEAVY_MASS_NUMBERS


HEAVY_ISOTOPES: Mapping[str, float] = _DynamicHeavyIsotopesMap()

def get_projection_matrix(coords: jnp.ndarray, masses: jnp.ndarray) -> jnp.ndarray:
    """Constructs the Eckart projection operator P = I - D D^T."""
    N = coords.shape[0]
    total_mass = jnp.sum(masses)

    # Center of mass
    com = jnp.sum(coords * masses[:, None], axis=0) / total_mass
    coords_shifted = coords - com

    sqrt_m = jnp.sqrt(masses)

    # Translations (3N x 3)
    T = jnp.zeros((3 * N, 3))
    T = T.at[0::3, 0].set(sqrt_m)
    T = T.at[1::3, 1].set(sqrt_m)
    T = T.at[2::3, 2].set(sqrt_m)

    # Rotations (3N x 3)
    R = jnp.zeros((3 * N, 3))
    x, y, z = coords_shifted[:, 0], coords_shifted[:, 1], coords_shifted[:, 2]

    # Rx
    R = R.at[1::3, 0].set(-z * sqrt_m)
    R = R.at[2::3, 0].set(y * sqrt_m)
    # Ry
    R = R.at[0::3, 1].set(z * sqrt_m)
    R = R.at[2::3, 1].set(-x * sqrt_m)
    # Rz
    R = R.at[0::3, 2].set(-y * sqrt_m)
    R = R.at[1::3, 2].set(x * sqrt_m)

    TR = jnp.concatenate((T, R), axis=1) # (3N, 6)

    # Robust projection onto orthogonal complement using pseudo-inverse
    # This correctly handles rank-deficient systems (e.g., linear molecules, single atoms)
    ident = jnp.eye(3 * N)
    P = ident - TR @ jnp.linalg.pinv(TR)
    return P

@jax.jit
def compute_freqs(masses_jax: jnp.ndarray, H_jax: jnp.ndarray, coords_jax: jnp.ndarray) -> jnp.ndarray:
    """Computes harmonic frequencies given masses, Hessian, and coordinates."""
    inv_sqrt_m = 1.0 / jnp.sqrt(masses_jax)
    inv_sqrt_m_3 = jnp.repeat(inv_sqrt_m, 3)

    # Mass weight the Hessian: H_mw = M^{-1/2} H M^{-1/2}
    H_mw = H_jax * inv_sqrt_m_3[:, None] * inv_sqrt_m_3[None, :]

    # Eckart Projection
    P = get_projection_matrix(coords_jax, masses_jax)
    H_proj = P @ H_mw @ P

    # Diagonalize
    eigenvalues, _ = jnp.linalg.eigh(H_proj)

    # Convert to cm^-1 (~5140.487 cm^-1 per atomic unit)
    freqs = jnp.sign(eigenvalues) * jnp.sqrt(jnp.abs(eigenvalues)) * 5140.4871447
    return freqs

def auto_kie_profiling(hdf5_path: str, group_name: str) -> None:
    """Automates heavy isotope KIE profiling for a given basin in PESStore."""
    if molsym is None:
        raise RuntimeError("molsym is not installed.")

    with h5py.File(hdf5_path, 'a') as f:
        if group_name not in f:
            raise KeyError(f"Group {group_name} not found in {hdf5_path}.")

        grp = f[group_name]

        if "unweighted_hessian" in grp:
            H = grp["unweighted_hessian"][:]
        elif "hessian" in grp:
            H = grp["hessian"][:]
        else:
            raise KeyError("unweighted_hessian dataset not found in HDF5 group.")

        if "xyz_coordinates" not in grp:
            raise KeyError("xyz_coordinates dataset not found in HDF5 group.")
        coords = grp["xyz_coordinates"][:]

        symbols = None
        if "symbols" in grp:
            symbols_dset = grp["symbols"][:]
            symbols = [s.decode('utf-8') if isinstance(s, bytes) else s for s in symbols_dset]
        elif "atomic_numbers" in grp:
            atomic_numbers = grp["atomic_numbers"][:]
            symbols = [pt.to_symbol(int(z)) for z in atomic_numbers]
        elif "molecule_name" in grp.attrs:
            # Maybe the geometry has elements? Not guaranteed.
            pass

        if symbols is None:
            raise KeyError("Neither symbols nor atomic_numbers found in HDF5 group to determine atomic masses.")

        # Ensure lengths match
        if len(symbols) * 3 != H.shape[0]:
            raise ValueError("Dimension mismatch between symbols and Hessian.")

        base_masses = np.array([pt.to_mass(s) for s in symbols])

        # Find symmetrically equivalent atoms
        mol = molsym.Molecule(symbols, coords, base_masses)
        seas = mol.find_SEAs()

        H_jax = jnp.array(H)
        coords_jax = jnp.array(coords)

        # Calculate frequencies for each representative atom
        for sea in seas:
            rep_idx = sea.subset[0]
            sym = symbols[rep_idx]

            if sym not in HEAVY_ISOTOPES:
                continue

            heavy_mass = HEAVY_ISOTOPES[sym]

            # Substitute mass
            new_masses = base_masses.copy()
            new_masses[rep_idx] = heavy_mass

            new_masses_jax = jnp.array(new_masses)

            freqs = compute_freqs(new_masses_jax, H_jax, coords_jax)

            dataset_name = f"frequencies_isotope_{rep_idx}"
            if dataset_name in grp:
                del grp[dataset_name]
            grp.create_dataset(dataset_name, data=np.array(freqs))
            logger.info(f"Committed KIE frequencies for heavy isotope at atom {rep_idx} ({sym})")
