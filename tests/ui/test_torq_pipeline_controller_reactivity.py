"""Physical Zero-Mock Test for TORQ Pipeline Controller Reactivity.

Validates Suggestion #46: State persistence, cache invalidation, SHA-256 provenance tracking,
and target preset switching without cross-contamination.
"""

import numpy as np
import pytest

from UI.cochem_torq_controller import TORQPipelineController, PipelineState


def test_torq_pipeline_controller_preset_switching_and_invalidation():
    """Assert switching presets recalculates SHA-256 and invalidates downstream caches."""
    controller = TORQPipelineController()
    assert controller.state.geometry_hash == ""
    assert controller.state.molecule_name == ""

    # 1. Load Hydrogen Peroxide preset
    h2o2_coords = np.array([
        [0.000000, 0.732100, -0.052400],
        [0.000000, -0.732100, -0.052400],
        [0.816600, 0.884100, 0.419200],
        [-0.816600, -0.884100, 0.419200],
    ], dtype=np.float64)
    h2o2_symbols = ["O", "O", "H", "H"]

    hash_h2o2 = controller.load_preset("Hydrogen Peroxide (H2O2)", h2o2_symbols, h2o2_coords)
    assert hash_h2o2 != ""
    assert controller.state.geometry_hash == hash_h2o2
    assert controller.state.molecule_name == "Hydrogen Peroxide (H2O2)"
    assert controller.state.pes_scan_completed is False
    assert controller.state.dvr_completed is False
    assert controller.state.spcat_completed is False

    # Simulate completed calculations in downstream cache
    controller.record_pes_scan({"scan_grid_deg": [0, 60, 120], "energies_kcal": [0.0, 3.2, 7.1]})
    controller.record_dvr({"splitting_mhz": 341850.0, "eigenvalues_cm1": [0.0, 11.4]})
    controller.record_spcat({"lines_count": 42})
    controller.set_rotational_constants({"A": 20245.8, "B": 10518.2, "C": 6878.3})

    assert controller.state.pes_scan_completed is True
    assert controller.state.dvr_completed is True
    assert controller.state.spcat_completed is True
    assert len(controller.state.results_cache) == 4
    assert "pes_scan" in controller.state.results_cache

    banner_h2o2 = controller.get_active_target_banner()
    assert "Hydrogen Peroxide (H2O2)" in banner_h2o2
    assert hash_h2o2[:16] in banner_h2o2

    # 2. Switch preset to Water Dimer
    water_dimer_coords = np.array([
        [-1.464, -0.010, 0.000],
        [-0.505, -0.031, 0.000],
        [-1.782, 0.892, 0.000],
        [1.442, 0.010, 0.000],
        [1.798, -0.428, 0.762],
        [1.798, -0.428, -0.762],
    ], dtype=np.float64)
    water_dimer_symbols = ["O", "H", "H", "O", "H", "H"]

    hash_dimer = controller.load_preset("Water Dimer ((H2O)2)", water_dimer_symbols, water_dimer_coords)

    # 3. Assert geometry SHA-256 changes immediately
    assert hash_dimer != hash_h2o2
    assert controller.state.geometry_hash == hash_dimer
    assert controller.state.molecule_name == "Water Dimer ((H2O)2)"

    # 4. Assert results_cache is completely purged and execution flags are reset
    assert len(controller.state.results_cache) == 0
    assert controller.state.pes_scan_completed is False
    assert controller.state.dvr_completed is False
    assert controller.state.spcat_completed is False
    assert controller.state.rotational_constants is None

    banner_dimer = controller.get_active_target_banner()
    assert "Water Dimer ((H2O)2)" in banner_dimer
    assert hash_dimer[:16] in banner_dimer
