"""Zero-mock unit test for Exact Permutation-Inversion Monomial Algebra & Group Invariance in PIP Featurization.

SRS Chunk 14 / Suggestion #136 / Method Matrix v4 §13.2 [M], [D].
Zero-Mock Mandate v3: Authentic 6-atom symmetric system and strict group invariance to < 10^-14 Eh.
"""

from __future__ import annotations

import math

import numpy as np

from cochem_base.core_engine.cochem_core_auto_pes import (
    GeometryFeaturizer,
    PipSymmetryConfig,
)


def test_pip_monomial_group_invariance_six_atom_system() -> None:
    """Verify PIP features remain invariant under arbitrary nuclear permutations in S_6 to < 10^-14 Eh [M], [D]."""
    # 6-atom symmetric system (e.g. 6 identical Hydrogen atoms / H6 ring or octahedral cluster)
    symbols = ["H", "H", "H", "H", "H", "H"]

    # Authentic 3D geometry of planar H6 ring with slight asymmetric perturbation
    r = 1.2
    angles = [i * (2.0 * math.pi / 6.0) for i in range(6)]
    coords = np.array(
        [[r * math.cos(a), r * math.sin(a), 0.05 * (i % 2)] for i, a in enumerate(angles)],
        dtype=np.float64,
    )

    pip_cfg = PipSymmetryConfig(
        subgroup_type="full",
        max_symmetric_order=720,  # 6! = 720
    )

    featurizer = GeometryFeaturizer(
        symbols=symbols,
        morse_lambda=1.5,
        include_secondary=True,
        pip_config=pip_cfg,
    )

    base_features = featurizer.featurize(coords)

    # Test permutations:
    # 1. 2-cycle transposition (0, 1)
    # 2. 3-cycle (0, 2, 4)
    # 3. 4-cycle (1, 3, 5, 2)
    # 4. Full reverse permutation (5, 4, 3, 2, 1, 0)
    permutations = [
        [1, 0, 2, 3, 4, 5],
        [2, 1, 4, 3, 0, 5],
        [0, 3, 1, 5, 4, 2],
        [5, 4, 3, 2, 1, 0],
    ]

    for p in permutations:
        permuted_coords = coords[p, :]
        perm_features = featurizer.featurize(permuted_coords)

        # Invariant monomial basis must be bit-for-bit / FP64 identical to < 10^-14
        diff = np.max(np.abs(base_features - perm_features))
        assert diff < 1e-14, (
            f"PIP feature broke group invariance under permutation {p}: max diff {diff:.2e} >= 1e-14"
        )
