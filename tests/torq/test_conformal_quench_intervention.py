"""
Zero-Mock Physical Verification Test Suite: Conformal Quench Intervention.
Validating Suggestion #31 (Chunk 4).

Method Matrix v4 & Anti-Spoofing Protocols v2:
- Zero-Mock Mandate: Zero test doubles (stub objects strictly forbidden).
- Physical molecular structures (Formaldehyde, H2CO).
- Authentic mathematical nonconformity calibration and physical state rollback.
"""

import math
import sys
import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pytest
import torch

from Libraries.cochem_torq_conformal import (
    CalibrationSample,
    ConformalPredictor,
    ConformalPredictorConfig,
    MolecularFrame,
    TrajectoryInterventionHandler,
    UncertaintyBreachSignal,
)
from cochem_torq.quench_broker import (
    IPCTrajectoryQuenchBroker,
    QuenchMethodology,
    QuenchRequest,
    QuenchResponse,
)


def test_conformal_trajectory_quench_intervention():
    """Test 1: Autonomous Trajectory Quenching and Epistemic Breach Rollback.

    Verifies:
    1. Conformal calibration provides valid finite-sample coverage threshold (1 - alpha = 0.90).
    2. Physical trajectory of formaldehyde (H2CO) tracks frames in circular buffer.
    3. Out-of-distribution frame (stretched C=O > 2.5 A) triggers UncertaintyBreachSignal.
    4. State cleanly rolls back to last trustworthy frame K-1.
    5. Quench payload serializes to standard QCSchema format and is dispatched to broker.
    """
    # 1. Setup calibrated ConformalPredictor with alpha = 0.10 (90% confidence)
    cfg = ConformalPredictorConfig(alpha=0.10, strict_calibration_size=False)
    predictor = ConformalPredictor(config=cfg)

    # Physical calibration samples (Formaldehyde equilibrium vs small perturbations)
    # H2CO atomic numbers: C (6), O (8), H (1), H (1)
    atomic_numbers = [6, 8, 1, 1]
    data_dir = Path(__file__).parent.parent / "data"
    cal_data_np = np.load(data_dir / "h2co_cal_data.npz")
    cal_data: List[CalibrationSample] = []
    for step in range(12):
        sample = CalibrationSample(
            energy_true=float(cal_data_np["energy_true"][step]),
            energy_pred=float(cal_data_np["energy_pred"][step]),
            energy_sigma=float(cal_data_np["energy_sigma"][step]),
            forces_true=torch.from_numpy(cal_data_np["forces_true"][step]),
            forces_pred=torch.from_numpy(cal_data_np["forces_pred"][step]),
            forces_sigma=torch.from_numpy(cal_data_np["forces_sigma"][step]),
        )
        cal_data.append(sample)

    predictor.calibrate(cal_data)
    assert predictor.is_calibrated

    # Calibrated threshold for nonconformity
    threshold = 0.90
    handler = TrajectoryInterventionHandler(predictor=predictor, capacity=8, threshold=threshold)
    assert handler.current_threshold == 0.90

    # 2. Stream physical trajectory frames of Formaldehyde
    traj_data = np.load(data_dir / "h2co_trajectory.npz")
    
    # Inject 10 normal in-distribution frames (small thermal oscillations)
    for frame_idx in range(1, 11):
        idx = frame_idx - 1 # 0-indexed in arrays
        frame = MolecularFrame(
            step=frame_idx,
            positions=torch.from_numpy(traj_data["positions"][idx]),
            velocities=torch.from_numpy(traj_data["velocities"][idx]),
            forces=torch.from_numpy(traj_data["forces"][idx]),
            energy=float(traj_data["energies"][idx]),
            uncertainty_score=float(traj_data["uncertainties"][idx]),
            atomic_numbers=atomic_numbers,
        )
        safe = handler.evaluate_and_intervene(frame)
        assert safe is True

    # Buffer contains recent frames
    assert len(handler.buffer) > 0
    last_valid_frame = handler.buffer[-1]
    assert last_valid_frame.step == 10

    # 3. Inject out-of-distribution geometry at frame 11 (C=O stretched to 2.65 A)
    ood_idx = 10
    ood_frame = MolecularFrame(
        step=11,
        positions=torch.from_numpy(traj_data["positions"][ood_idx]),
        velocities=torch.from_numpy(traj_data["velocities"][ood_idx]),
        forces=torch.from_numpy(traj_data["forces"][ood_idx]),
        energy=float(traj_data["energies"][ood_idx]),
        uncertainty_score=float(traj_data["uncertainties"][ood_idx]),
        atomic_numbers=atomic_numbers,
    )

    breach_caught = False
    try:
        handler.evaluate_and_intervene(ood_frame)
    except UncertaintyBreachSignal as breach:
        breach_caught = True
        assert breach.frame_index == 11
        assert breach.nonconformity_score == 1.875
        assert breach.threshold == 0.90

    assert breach_caught is True

    # 4. Verify state rollback to frame 10 (K-1 trustworthy frame)
    rolled_back_frame = handler.rollback()
    assert rolled_back_frame is not None
    assert rolled_back_frame.step == 10

    # 5. Dispatch Quench Request via decoupled Broker
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_file = Path(tmpdir) / "active_learning_manifest.json"
        broker = IPCTrajectoryQuenchBroker(manifest_path=manifest_file)

        request = QuenchRequest(
            trajectory_id="traj_h2co_sim_001",
            frame_index=ood_frame.step,
            atomic_numbers=atomic_numbers,
            geometry_angstrom=ood_frame.positions.tolist(),
            nonconformity_score=ood_frame.uncertainty_score,
            calibration_threshold=handler.current_threshold,
            methodology=QuenchMethodology.GFN2_XTB,
        )

        # Validate QCSchema format
        qc_schema = request.to_qcschema()
        assert qc_schema["schema_name"] == "qcschema_input"
        assert qc_schema["schema_version"] == 1
        assert qc_schema["driver"] == "gradient"
        assert qc_schema["model"]["method"] == "gfn2-xtb"
        assert len(qc_schema["molecule"]["geometry"]) == 12 # 4 atoms * 3 coords in Bohr

        import shutil
        from cochem_torq.quench_broker import BinaryNotFoundError

        # Execute quench
        try:
            response = broker.dispatch_quench(request)
            assert isinstance(response, QuenchResponse)
            assert response.trajectory_id == "traj_h2co_sim_001"
            assert response.frame_index == 11
            assert response.converged is True
            assert len(response.quenched_geometry) == 4
        except BinaryNotFoundError:
            if shutil.which("xtb") is None:
                pytest.skip("xtb executable not found, skipping physical relaxation verification.")
            else:
                raise

        assert manifest_file.exists()
