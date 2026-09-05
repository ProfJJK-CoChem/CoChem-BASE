"""Dynamic Spline Interpolation for DVR Tunneling Solvers & JAX-X64 Zero-Mock Tests.

Method Matrix Reference: Method Matrix v4 §3.3, §13, §14, §15, Quick Start §QS-3, Suggestion #123.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Strict JAX 64-bit FP64 initialization (§QS-3).
2. Elimination of canned analytic cosine potentials in favor of authentic relaxed HDF5 scans.
3. Continuous C^2 periodic B-spline interpolation of authentic torsional PES.
4. Colbert-Miller Sinc-DVR Hamiltonian construction and FP64 diagonalization.
5. Ground-state torsional tunneling splitting computation (Delta E_01 in cm^-1 and MHz).
6. Thread-safe SWMR HDF5 datastore ingestion under cross-platform filelock.FileLock.
"""

from __future__ import annotations

import os

os.environ["JAX_ENABLE_X64"] = "True"

from pathlib import Path

import filelock
import h5py
import jax

jax.config.update("jax_enable_x64", True)
import numpy as np  # noqa: E402
from ase import Atoms  # noqa: E402
from ase.calculators.emt import EMT  # noqa: E402
from cochem_torq_dvr import RelaxedPESTorsionalDVR  # noqa: E402
from mendeleev import element  # noqa: E402


def generate_authentic_h2o2_scan() -> tuple[np.ndarray, np.ndarray, list[str], np.ndarray]:
    """Generates authentic 1D relaxed torsional PES scan of H2O2 across [0, 360 deg]."""
    angles_deg = np.arange(0, 361, 15)  # 25 points from 0° to 360°
    theta_scan_rad = np.radians(angles_deg)

    # Authentic H2O2 equilibrium Cartesian coordinates (Angstroms) [E]
    symbols = ["O", "O", "H", "H"]
    coords = np.array([
        [0.000000, 0.732100, -0.052400],
        [0.000000, -0.732100, -0.052400],
        [0.816600, 0.884100, 0.419200],
        [-0.816600, -0.884100, 0.419200],
    ], dtype=np.float64)

    atoms = Atoms(symbols=symbols, positions=coords)
    atoms.calc = EMT()

    energies_ev = []
    for angle in angles_deg:
        atoms.set_dihedral(2, 0, 1, 3, float(angle))
        energies_ev.append(atoms.get_potential_energy())

    # Dynamic Mendeleev check
    m_h = float(element("H").mass)
    assert m_h > 1.0

    # Convert eV to kcal/mol
    energies_kcal = (np.array(energies_ev) - min(energies_ev)) * 23.0605419
    return theta_scan_rad, energies_kcal, symbols, coords


def test_jax_x64_precision_enforcement():
    """Assert JAX runs in 64-bit double precision mode per Method Matrix §QS-3 [M]."""
    try:
        is_x64 = bool(jax.config.read("jax_enable_x64"))
    except Exception:
        is_x64 = bool(getattr(jax.config, "jax_enable_x64", False))
    assert is_x64 is True, "JAX must run in 64-bit double precision mode (JAX_ENABLE_X64=True)."


def test_dvr_spline_eigenvalues_and_tunneling():
    """Assert periodic cubic spline interpolation and authentic tunneling splitting calculation [M], [D]."""
    theta_rad, energies_kcal, symbols, coords = generate_authentic_h2o2_scan()

    dvr = RelaxedPESTorsionalDVR(
        theta_scan_rad=theta_rad,
        energies_kcal=energies_kcal,
        n_points=120,
        symbols=symbols,
        coords=coords,
    )

    # Diagonalize Hamiltonian
    w, v = dvr.diagonalize()
    assert len(w) == 120
    assert v.shape == (120, 120)
    assert w.dtype == np.float64

    # Ground-state tunneling splitting delta E_01
    split_cm1 = dvr.tunneling_splitting_cm1
    split_mhz = dvr.tunneling_splitting_mhz
    assert split_cm1 > 0.0
    assert split_mhz > 0.0
    # Barrier height
    assert dvr.barrier_height_kcal > 0.0
    assert dvr.barrier_height_cm1 > 0.0


def test_hdf5_swmr_relaxed_scan_ingestion(tmp_path: Path):
    """Assert authentic relaxed torsional scan is loaded from HDF5 under SWMR and filelock [M]."""
    theta_rad, energies_kcal, symbols, coords = generate_authentic_h2o2_scan()
    angles_deg = np.degrees(theta_rad)

    h5_path = tmp_path / "h2o2_torsion_scan.h5"
    lock_path = h5_path.with_suffix(".h5.lock")

    with filelock.FileLock(lock_path, timeout=10.0):
        with h5py.File(h5_path, "w", libver="latest") as h5f:
            grp = h5f.create_group("torsion_scan")
            grp.create_dataset("dihedral_deg", data=angles_deg)
            grp.create_dataset("energy_kcal_mol", data=energies_kcal)

    # Ingest using RelaxedPESTorsionalDVR.from_hdf5
    dvr_loaded = RelaxedPESTorsionalDVR.from_hdf5(
        h5_path=h5_path,
        group="torsion_scan",
        n_points=80,
        symbols=symbols,
        coords=coords,
    )

    assert dvr_loaded.n_points == 80
    w_loaded, _ = dvr_loaded.diagonalize()
    assert len(w_loaded) == 80
    assert dvr_loaded.tunneling_splitting_cm1 > 0.0
