import os
os.environ["JAX_ENABLE_X64"] = "True"

import numpy as np
import pytest
from mendeleev import element

from cochem_base.core_engine.cochem_core_auto_pes import ExactKernelRidgeEstimator
from cochem_base.schemas import KrrRegularizationConfig


def test_krr_numerical_conditioning_and_anchor_floor():
    """Verify KRR anchor regularization floor >= 1e-8 Ha and Cholesky jitter escalation (Suggestion #58 / Method Matrix v4 §8C, §13.2 [M], [D])."""
    # Dynamic Mendeleev check
    ar_elem = element("Ar")
    assert ar_elem.atomic_number == 18

    from ase import Atoms
    from ase.calculators.emt import EMT
    from ase.md.verlet import VelocityVerlet
    from ase import units

    # 1. Construct dataset with 5 asymptotic dissociation points where r > 10 A
    # Physical states using ASE EMT
    atoms = Atoms("CuAg", positions=[[0,0,0], [2.5,0,0]])
    atoms.calc = EMT()

    # Near equilibrium: 10 points
    atoms.set_velocities([[0.01, 0, 0], [-0.01, 0, 0]])
    dyn1 = VelocityVerlet(atoms, 1.0 * units.fs)
    r_eq_geoms = []
    y_eq = []
    for _ in range(10):
        dyn1.run(5)
        r_eq_geoms.append(atoms.get_positions())
        y_eq.append(atoms.get_potential_energy())

    # Asymptotic dissociation: 5 points where r > 12 A
    atoms.set_positions([[0,0,0], [12.0, 0, 0]])
    atoms.set_velocities([[0.01, 0, 0], [0.01, 0, 0]])
    dyn2 = VelocityVerlet(atoms, 1.0 * units.fs)
    r_asymp_geoms = []
    y_asymp = []
    for _ in range(5):
        dyn2.run(5)
        r_asymp_geoms.append(atoms.get_positions())
        y_asymp.append(atoms.get_potential_energy())

    X_geoms = np.vstack([r_eq_geoms, r_asymp_geoms])
    dists = np.linalg.norm(X_geoms[:, 0, :] - X_geoms[:, 1, :], axis=1)
    # 1D features: y_ij
    X = np.exp(-dists / 2.0).reshape(-1, 1)

    y_raw = np.concatenate([y_eq, y_asymp])
    # Target y: shift so asymptotic energy is ~ 0 for anchor floor testing
    y = y_raw - np.mean(y_asymp)

    # Verify that raw Gram matrix of asymptotic points is ill-conditioned:
    # Kernel: K_ij = exp(-gamma * ||x_i - x_j||^2)
    gamma = 10.0
    diff = X - X.T
    K_raw = np.exp(-gamma * (diff ** 2))
    eigenvalues = np.linalg.eigvalsh(K_raw)
    min_eig = np.min(eigenvalues)
    # Because 5 asymptotic points have features extremely close to 0 (exp(-12/2) ~ 0.002),
    # the raw Gram matrix eigenvalues drop below 1e-12:
    assert min_eig < 1e-10, f"Raw Gram matrix not ill-conditioned enough: min_eig={min_eig}"

    # 2. Fit KRR using strict regularization floor 1e-8 Ha and adaptive jitter 1e-9 [M]
    reg_cfg = KrrRegularizationConfig(
        base_alpha=1e-8,
        anchor_alpha_floor=1e-8,
        jitter_epsilon=1e-9,
        max_jitter_escalation=1e-6,
    )
    krr = ExactKernelRidgeEstimator(
        gamma=gamma,
        alpha=1e-8,
        regularization_config=reg_cfg,
    )

    # Fitting must succeed without LinAlgError [M]
    krr.fit(X, y)
    assert krr.is_fitted
    assert krr.alpha_vector is not None
    assert len(krr.alpha_vector) == len(X)

    # Predictions must evaluate stably without NaNs or Infs
    preds = krr.predict(X)
    assert not np.isnan(preds).any()
    assert not np.isinf(preds).any()
    mae = np.mean(np.abs(preds - y))
    assert mae < 0.01, f"KRR fit error unexpectedly large: MAE={mae}"
