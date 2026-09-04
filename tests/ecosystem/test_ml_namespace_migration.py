import os
os.environ["JAX_ENABLE_X64"] = "True"

from pathlib import Path
import pytest
from mendeleev import element


def test_torq_modules_relocation_and_base_absence():
    """Verify all 40 cochem_torq_* modules reside in CoChem-TORQ/Libraries and are absent from CoChem-BASE/Libraries (Suggestion #59 / Ecosystem Cohesion [M])."""
    # Dynamic Mendeleev check
    fe = element("Fe")
    assert fe.atomic_number == 26

    # Resolve repository roots
    base_repo = Path(__file__).resolve().parent.parent.parent
    torq_repo = (base_repo.parent / "CoChem-TORQ").resolve()

    base_libs_dir = base_repo / "Libraries"
    torq_libs_dir = torq_repo / "Libraries"

    # 1. Assert exactly 0 cochem_torq_* files in CoChem-BASE/Libraries
    base_torq_files = [f.name for f in base_libs_dir.glob("cochem_torq_*.py")]
    assert len(base_torq_files) == 0, f"Found unexpected residual cochem_torq modules in BASE: {base_torq_files}"

    # 2. Assert all 40 relocated modules are present in CoChem-TORQ/Libraries
    expected_modules = [
        "cochem_torq_active_learning.py",
        "cochem_torq_amp_trainer.py",
        "cochem_torq_ani2x_transfer.py",
        "cochem_torq_c2_cutoff.py",
        "cochem_torq_committee_ensemble.py",
        "cochem_torq_conformal.py",
        "cochem_torq_delta_ml.py",
        "cochem_torq_dispersion_d3.py",
        "cochem_torq_distributed_early_stopping.py",
        "cochem_torq_dynamic_batch.py",
        "cochem_torq_environment.py",
        "cochem_torq_finite_difference.py",
        "cochem_torq_force_matching.py",
        "cochem_torq_gnn_debugger.py",
        "cochem_torq_gnn_scheduler.py",
        "cochem_torq_gradient_checkpointing.py",
        "cochem_torq_graph_pruning.py",
        "cochem_torq_hdf5_datamodule.py",
        "cochem_torq_hpo.py",
        "cochem_torq_inference_errors.py",
        "cochem_torq_inference_schemas.py",
        "cochem_torq_lbfgs_optimizer.py",
        "cochem_torq_loss_landscape.py",
        "cochem_torq_masses.py",
        "cochem_torq_md_env.py",
        "cochem_torq_md_errors.py",
        "cochem_torq_md_schemas.py",
        "cochem_torq_multitask.py",
        "cochem_torq_neighbor_list.py",
        "cochem_torq_onnx_export.py",
        "cochem_torq_pbc_graph.py",
        "cochem_torq_remd.py",
        "cochem_torq_storage.py",
        "cochem_torq_symplectic.py",
        "cochem_torq_torchscript_export.py",
        "cochem_torq_training_errors.py",
        "cochem_torq_training_persistence.py",
        "cochem_torq_training_schemas.py",
        "cochem_torq_trajectory.py",
        "cochem_torq_vibrational.py",
    ]
    assert len(expected_modules) == 40

    for mod_name in expected_modules:
        mod_path = torq_libs_dir / mod_name
        assert mod_path.is_file(), f"Relocated module missing in TORQ/Libraries: {mod_name}"


def test_cochem_ml_public_namespace_api():
    """Verify clean import and instantiation of public API classes via cochem.ml namespace (Suggestion #59 [M])."""
    from cochem.ml.active_learning import ActiveLearningBatchConfig, ActiveLearningEngine
    from cochem.ml.conformal import ConformalCalibrationConfig, ConformalPredictor
    from cochem.ml.delta import DeltaMLDispersionConfig, DeltaMLEngine
    from cochem.ml.models import ANI2xModel, ForceMatchingLoss

    # 1. Instantiate Active Learning Engine & Config
    al_cfg = ActiveLearningBatchConfig(batch_size=16, repulsion_length_scale=0.5, diversity_weight=0.8)
    al_engine = ActiveLearningEngine(batch_config=al_cfg)
    assert al_engine.batch_config.batch_size == 16

    # 2. Instantiate Delta-ML Engine & D3 Dispersion Config
    delta_cfg = DeltaMLDispersionConfig(use_d3_dispersion=True, s6_scale=1.0)
    delta_engine = DeltaMLEngine(config=delta_cfg)
    assert delta_engine.use_d3_dispersion is True

    # 3. Instantiate Conformal Predictor & Config
    conf_cfg = ConformalCalibrationConfig(significance_level=0.05, min_calibration_observations=20)
    conf_predictor = ConformalPredictor(config=conf_cfg)
    assert conf_predictor.alpha == 0.05

    # 4. Instantiate Models: ANI2x & ForceMatchingLoss
    ani_model = ANI2xModel(species_list=[1, 6, 7, 8], feature_dim_per_species=16)
    assert ani_model is not None

    loss_fn = ForceMatchingLoss()
    assert loss_fn is not None
