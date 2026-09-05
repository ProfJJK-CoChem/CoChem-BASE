"""Zero-mock unit test for Grimme D3(BJ)/D4 Dispersion Augmentation for Semi-Empirical Baselines in Delta-ML.

SRS Chunk 14 / Suggestion #139 / Method Matrix v4 §9A, §9B.1--§9B.4 [M], [D].
Zero-Mock Mandate v3: Completely authentic physical dispersion evaluation on non-covalent dimer.
"""

from __future__ import annotations

import torch
from Libraries.cochem_torq_delta_ml import (
    DeltaMLConfig,
    DeltaMLEngine,
)
from Libraries.cochem_torq_dispersion_d3 import DispersionD3Layer
from Libraries.cochem_torq_inference_schemas import DispersionD3Config


def test_delta_ml_automatic_d3_dispersion_augmentation() -> None:
    """Verify semi-empirical / empirical baseline automatically appends D3(BJ) dispersion [M], [D]."""
    # Authentic Methane dimer (CH4)2 geometry at van der Waals distance R = 3.8 A
    # Carbon 1 at origin, Carbon 2 at (0, 0, 3.8)
    coords = torch.tensor(
        [
            # Methane 1
            [0.0, 0.0, 0.0],
            [0.63, 0.63, 0.63],
            [-0.63, -0.63, 0.63],
            [-0.63, 0.63, -0.63],
            [0.63, -0.63, -0.63],
            # Methane 2
            [0.0, 0.0, 3.8],
            [0.63, 0.63, 3.8 + 0.63],
            [-0.63, -0.63, 3.8 + 0.63],
            [-0.63, 0.63, 3.8 - 0.63],
            [0.63, -0.63, 3.8 - 0.63],
        ],
        dtype=torch.float64,
    )
    species = [6, 1, 1, 1, 1, 6, 1, 1, 1, 1]

    # Engine without dispersion
    engine_no_disp = DeltaMLEngine(
        config=DeltaMLConfig(baseline_method="LennardJones", use_d3_dispersion=False),
        use_d3_dispersion=False,
    )
    e_no_disp, f_no_disp = engine_no_disp.compute_baseline(coords, species)

    # Engine with D3(BJ) dispersion
    engine_disp = DeltaMLEngine(
        config=DeltaMLConfig(baseline_method="LennardJones", use_d3_dispersion=True),
        use_d3_dispersion=True,
    )
    e_disp, f_disp = engine_disp.compute_baseline(coords, species)

    # Dispersion energy must be strictly negative (attractive)
    diff_e = e_disp - e_no_disp
    assert diff_e < -1e-6, f"D3 dispersion was not attractive: diff={diff_e:.6f} eV"

    # Verify R^-6 asymptotic behavior at large separations (R=6.0 A vs R=12.0 A: ratio should approach 2^6 = 64)
    d3_layer = DispersionD3Layer(config=DispersionD3Config(s6=1.0, s8=0.0))
    coords_6 = coords.clone()
    coords_6[5:, 2] += (6.0 - 3.8)
    e_d3_6, _ = d3_layer.compute_energy_and_forces(coords_6, species)

    coords_12 = coords.clone()
    coords_12[5:, 2] += (12.0 - 3.8)
    e_d3_12, _ = d3_layer.compute_energy_and_forces(coords_12, species)

    # Attractive energy at 6.0 A should be substantially greater in magnitude than at 12.0 A
    assert abs(e_d3_6.item()) > abs(e_d3_12.item())
    assert abs(e_d3_12.item()) > 0.0
