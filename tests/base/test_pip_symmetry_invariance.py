import os
os.environ["JAX_ENABLE_X64"] = "True"

import numpy as np
import pytest
from mendeleev import element

from cochem_base.core_engine.cochem_core_auto_pes import (
    ExactKernelRidgeEstimator,
    GeometryFeaturizer,
)
from cochem_base.schemas import PipSymmetryConfig


def test_pip_closed_subgroup_energy_degeneracy():
    """Verify algebraic subgroup wreath product PIP orbit averaging satisfies exact permutation energy degeneracy |E(PX) - E(X)| < 1e-14 Eh (Suggestion #57 / Method Matrix v4 §13.2 [M], [D])."""
    # Dynamic Mendeleev check: 6 identical Hydrogens
    h_elem = element("H")
    assert h_elem.atomic_number == 1
    assert h_elem.mass is not None

    symbols = ["H"] * 6
    pip_cfg = PipSymmetryConfig(
        max_symmetric_order=120,
        subgroup_type="automorphism_wreath",
        invariance_tolerance=1e-14,
    )
    featurizer = GeometryFeaturizer(symbols=symbols, pip_config=pip_cfg)

    # Verify algebraic group closure has been strictly verified and subgroup has order 48
    assert len(featurizer.group_permutations) == 48

    # 6-atom coordinate matrix
    coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.1, 0.0, 0.0],
            [0.0, 1.2, 0.0],
            [1.1, 1.2, 0.0],
            [0.55, 0.6, 1.0],
            [0.55, 0.6, -1.0],
        ],
        dtype=np.float64,
    )

    f_orig = featurizer.compute_morse_features(coords)

    # Fit an exact KRR estimator with training data
    krr = ExactKernelRidgeEstimator()
    krr.fit(f_orig.reshape(1, -1), np.array([-3.25]))

    e_orig = krr.predict(f_orig.reshape(1, -1))[0]

    # Evaluate potential energy under all 48 permutations P in G
    max_energy_variation = 0.0
    for perm in featurizer.group_permutations:
        perm_coords = coords[list(perm)]
        f_perm = featurizer.compute_morse_features(perm_coords)
        e_perm = krr.predict(f_perm.reshape(1, -1))[0]
        variation = abs(e_perm - e_orig)
        if variation > max_energy_variation:
            max_energy_variation = variation

    # Assert exact degeneracy: max |E(PX) - E(X)| < 1e-14 Eh [M]
    assert (
        max_energy_variation < 1e-14
    ), f"PIP symmetry violation: max |E(PX) - E(X)| = {max_energy_variation:.4e} Eh >= 1e-14 Eh"
