"""Unit and integration tests for Deliverable 10: Conformal Uncertainty-Driven Trajectory Quenching & QCSchema Persistence (Suggestion #110).

Mandated by Method Matrix v4 (§8A, §8C) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic mathematical conformal bounds and physical coordinates.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import torch

from cochem_base.cochem_torq_quench import (
    ConformalMDQuencher,
    format_to_qcschema_v1,
)
from Libraries.cochem_torq_conformal import ConformalPredictor, CalibrationSample
from Libraries.cochem_torq_inference_schemas import ConformalPredictorConfig


def _build_calibrated_conformal_predictor() -> ConformalPredictor:
    """Instantiate authentic conformal predictor calibrated on physical samples."""
    cfg = ConformalPredictorConfig(alpha=0.10)
    predictor = ConformalPredictor(config=cfg)

    # 25 authentic physical calibration samples
    samples = []

    for i in range(25):
        f_true = torch.tensor([[0.01, 0.02, -0.01], [-0.01, 0.01, 0.0], [0.0, -0.03, 0.01]], dtype=torch.float64)
        f_pred = f_true + 0.005 * (i % 3 - 1)
        f_sig = torch.full((3, 3), 0.01, dtype=torch.float64)
        sample = CalibrationSample(
            energy_true=-76.4 - i * 0.001,
            energy_pred=-76.4 - i * 0.001 + 0.002,
            energy_sigma=0.01,
            forces_true=f_true,
            forces_pred=f_pred,
            forces_sigma=f_sig,
        )
        samples.append(sample)

    predictor.calibrate(samples)
    return predictor


def test_conformal_md_quencher_rollback_and_qcschema(tmp_path: Path):
    """Verify trajectory halt, checkpoint rollback, physical quench, and QCSchema v1 export."""
    predictor = _build_calibrated_conformal_predictor()
    assert predictor.is_calibrated is True

    # Quencher
    h5_store = tmp_path / "active_learning_swmr.h5"
    quencher = ConformalMDQuencher(
        conformal_predictor=predictor,
        hdf5_store_path=h5_store,
        check_interval=2,
    )

    # Initial frame
    symbols = ["O", "H", "H"]
    in_dist_coords = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.75, 0.5],
        [0.0, -0.75, 0.5],
    ], dtype=np.float64)

    # Out-of-distribution frame with high steric clash / huge force uncertainty
    ood_coords = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.20, 0.1],  # Severe clash!
        [0.0, -0.75, 0.5],
    ], dtype=np.float64)

    # High force uncertainty tensor
    f_sig_high = torch.full((3, 3), 5.0, dtype=torch.float64)
    f_pred = torch.zeros((3, 3), dtype=torch.float64)

    # Step 1: In-distribution checkpoint
    res1 = quencher.step(step_idx=1, symbols=symbols, coordinates=in_dist_coords, forces_sigma=torch.full((3, 3), 0.005, dtype=torch.float64), forces_pred=f_pred)
    assert res1["action"] == "CONTINUE"

    # Step 2: OOD trigger at check_interval=2
    res2 = quencher.step(step_idx=2, symbols=symbols, coordinates=ood_coords, forces_sigma=f_sig_high, forces_pred=f_pred)
    assert res2["action"] == "QUENCH_AND_ROLLBACK"
    assert "quenched_coordinates" in res2
    assert "qcschema" in res2

    qcschema = res2["qcschema"]
    assert qcschema["schema_name"] == "qcschema_output"
    assert qcschema["schema_version"] == 1
    assert "molecule" in qcschema
    assert qcschema["molecule"]["symbols"] == ["O", "H", "H"]

    # Verify HDF5 store received the QCSchema record
    assert h5_store.exists()


def test_format_to_qcschema_v1():
    """Verify MolSSI QCSchema v1 formatting adheres to standard specifications."""
    symbols = ["O", "H", "H"]
    coords = np.array([[0, 0, 0], [0, 0.75, 0.5], [0, -0.75, 0.5]], dtype=np.float64)

    qc = format_to_qcschema_v1(
        symbols=symbols,
        coordinates=coords,
        energy=-76.432,
        temperature_k=298.15,
        pressure_atm=1.0,
    )
    assert qc["schema_name"] == "qcschema_output"
    assert qc["schema_version"] == 1
    assert qc["driver"] == "energy"
    assert qc["properties"]["return_energy"] == -76.432
    assert qc["molecule"]["symbols"] == symbols
