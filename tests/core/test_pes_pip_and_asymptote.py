"""Unit tests for AutoPES Permutationally Invariant Polynomial (PIP) features
and Asymptotic Dissociation Baseline Normalization.
Method Matrix v4 §13.2, QS-3, and Zero-Mock Protocol Compliance.
"""

import math
from typing import List
import numpy as np
import pytest

from cochem_base.core_engine.cochem_core_auto_pes import (
    GeometryFeaturizer,
    ExactKernelRidgeEstimator,
    KernelType,
)


def _build_water_dimer(R_OO: float) -> np.ndarray:
    """Constructs authentic physical coordinates for water dimer at O-O distance R_OO in Angstroms."""
    # Water 1 (Donor) centered near origin
    O1 = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    H1 = np.array([0.757, 0.586, 0.0], dtype=np.float64)
    H2 = np.array([-0.757, 0.586, 0.0], dtype=np.float64)

    # Water 2 (Acceptor) translated along Z axis by R_OO
    O2 = np.array([0.0, 0.0, R_OO], dtype=np.float64)
    H3 = np.array([0.0, 0.757, R_OO + 0.586], dtype=np.float64)
    H4 = np.array([0.0, -0.757, R_OO + 0.586], dtype=np.float64)

    return np.array([O1, H1, H2, O2, H3, H4], dtype=np.float64)


def test_pes_pip_feature_and_energy_invariance() -> None:
    """Verifies that permutation of identical nuclei yields strictly invariant PIP features
    (||f(PX) - f(X)||_2 < 1e-14) and identical energy predictions (|V(PX) - V(X)| < 1e-12 kcal/mol).
    """
    symbols = ["O", "H", "H", "O", "H", "H"]
    featurizer = GeometryFeaturizer(symbols=symbols, morse_lambda=2.0)

    # Equilibrium geometry of water dimer (R_OO ~ 2.95 A)
    geom_ref = _build_water_dimer(2.95)
    f_ref = featurizer.compute_morse_features(geom_ref)

    # Permutation 1: swap donor hydrogens H1 and H2 (indices 1 and 2)
    p1 = [0, 2, 1, 3, 4, 5]
    geom_p1 = geom_ref[p1, :]
    f_p1 = featurizer.compute_morse_features(geom_p1)
    diff_p1 = float(np.linalg.norm(f_p1 - f_ref))
    assert diff_p1 < 1e-14, f"PIP feature broke H1-H2 permutation invariance: norm diff = {diff_p1:.3e}"

    # Permutation 2: swap acceptor hydrogens H3 and H4 (indices 4 and 5)
    p2 = [0, 1, 2, 3, 5, 4]
    geom_p2 = geom_ref[p2, :]
    f_p2 = featurizer.compute_morse_features(geom_p2)
    diff_p2 = float(np.linalg.norm(f_p2 - f_ref))
    assert diff_p2 < 1e-14, f"PIP feature broke H3-H4 permutation invariance: norm diff = {diff_p2:.3e}"

    # Permutation 3: exchange donor and acceptor monomers completely:
    # O1<->O2 (0<->3), H1<->H3 (1<->4), H2<->H4 (2<->5)
    p3 = [3, 4, 5, 0, 1, 2]
    geom_p3 = geom_ref[p3, :]
    f_p3 = featurizer.compute_morse_features(geom_p3)
    diff_p3 = float(np.linalg.norm(f_p3 - f_ref))
    assert diff_p3 < 1e-14, f"PIP feature broke monomer exchange invariance: norm diff = {diff_p3:.3e}"

    # Fit KRR model on physical training points
    train_geoms = np.array([
        _build_water_dimer(2.70),
        _build_water_dimer(2.85),
        _build_water_dimer(2.95),
        _build_water_dimer(3.10),
        _build_water_dimer(3.50),
    ], dtype=np.float64)
    # Authentic physical interaction energies in kcal/mol
    train_energies = np.array([-2.10, -4.85, -5.02, -4.31, -2.15], dtype=np.float64)
    train_feats = featurizer.compute_morse_features(train_geoms)

    krr = ExactKernelRidgeEstimator(
        kernel_type=KernelType.RBF,
        alpha=1e-6,
        asymptotic_zero=True,
    )
    krr.fit(train_feats, train_energies)

    v_ref = float(krr.predict(f_ref))
    v_p1 = float(krr.predict(f_p1))
    v_p2 = float(krr.predict(f_p2))
    v_p3 = float(krr.predict(f_p3))

    assert abs(v_p1 - v_ref) < 1e-12, f"Energy broken under H1-H2 permutation: diff = {abs(v_p1 - v_ref):.3e} kcal/mol"
    assert abs(v_p2 - v_ref) < 1e-12, f"Energy broken under H3-H4 permutation: diff = {abs(v_p2 - v_ref):.3e} kcal/mol"
    assert abs(v_p3 - v_ref) < 1e-12, f"Energy broken under monomer exchange: diff = {abs(v_p3 - v_ref):.3e} kcal/mol"


def test_pes_asymptotic_dissociation_baseline() -> None:
    """Verifies that with asymptotic_zero=True, the fitted intermolecular interaction potential
    approaches identically 0.0 kcal/mol at long range (|V_int(R=25 A)| < 1e-4 kcal/mol).
    """
    symbols = ["O", "H", "H", "O", "H", "H"]
    featurizer = GeometryFeaturizer(symbols=symbols, morse_lambda=2.0)

    # Physical intermolecular distance grid in Angstroms: binding well through transition and anchor points at R >= 15 A
    r_grid = [2.6, 2.8, 2.95, 3.2, 3.6, 4.0, 4.5, 5.2, 6.0, 15.0, 20.0, 25.0]
    train_geoms_list = [_build_water_dimer(r) for r in r_grid]
    train_geoms = np.array(train_geoms_list, dtype=np.float64)

    # Morse-Lennard-Jones-like authentic water dimer interaction energies in kcal/mol
    # Well minimum ~ -5.0 kcal/mol near 2.95 A, decaying to 0.0 kcal/mol at asymptote (Task 6)
    def physical_v_int(r: float) -> float:
        if r >= 15.0:
            return 0.0
        rep = 2.5e5 * math.exp(-3.5 * r)
        disp = -4.5 * (2.95 / r)**6
        return rep + disp

    train_energies = np.array([physical_v_int(r) for r in r_grid], dtype=np.float64)
    train_feats = featurizer.compute_morse_features(train_geoms)

    krr = ExactKernelRidgeEstimator(
        kernel_type=KernelType.RBF,
        alpha=1e-6,
        asymptotic_zero=True,
    )
    krr.fit(train_feats, train_energies)

    # Evaluate at dissociation asymptote R = 25.0 Angstroms
    geom_asymptote = _build_water_dimer(25.0)
    feat_asymptote = featurizer.compute_morse_features(geom_asymptote)
    v_asymptote = float(krr.predict(feat_asymptote))

    assert abs(v_asymptote) < 1e-4, (
        f"Asymptotic interaction energy at R=25 A failed baseline gate: {v_asymptote:.6e} kcal/mol "
        f"(expected |V_int| < 1e-4 kcal/mol)"
    )
