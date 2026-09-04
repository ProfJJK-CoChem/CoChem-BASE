"""CoChem-TORQ Training Dynamics, Transfer Learning, and Production Compilation Suite.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
"""

from __future__ import annotations

from pathlib import Path

# Extend package search path to include sibling CoChem-TORQ/Libraries
_torq_lib = (Path(__file__).resolve().parent.parent.parent / "CoChem-TORQ" / "Libraries").resolve()
if _torq_lib.is_dir() and str(_torq_lib) not in __path__:
    __path__.append(str(_torq_lib))

# Domain Errors
from Libraries.cochem_torq_training_errors import (
    CheckpointCorruptionError,
    CoChemError,
    CoChemTorqError,
    DiscontinuousForceError,
    DistributedSyncError,
    EquivarianceBreakError,
    HDF5LockTimeoutError,
    NonReciprocalGraphError,
    OOMRecoveryError,
    ParityVerificationError,
    PrecisionDivergenceError,
    SchedulerDivergenceError,
    TorqTrainingError,
    UnsupportedElementError,
)

# Pydantic v2 Schemas
from Libraries.cochem_torq_training_schemas import (
    C2GraphPrunerConfig,
    DistributedEarlyStoppingConfig,
    DynamicBatchScalerConfig,
    ForceMatchingLossConfig,
    GNNWarmRestartSchedulerConfig,
    LossLandscapeConfig,
    TorchScriptExportConfig,
    TrainingDynamicsConfig,
    TransferLearningConfig,
)

# Dynamic Mendeleev Masses
from Libraries.cochem_torq_masses import (
    get_atomic_masses,
    get_monoisotopic_mass,
    get_monoisotopic_masses,
    get_monoisotopic_masses_tensor,
    resolve_ciaaw_monoisotopic_mass,
)


# GNN Warm Restart Scheduler
from Libraries.cochem_torq_gnn_scheduler import (
    GNNWarmRestartScheduler,
    check_and_clip_gradients,
    compute_lr_at_step,
)

# Force-Matching Loss Engine
from Libraries.cochem_torq_force_matching import (
    ForceMatchingLoss,
    compute_angular_cosine_similarity,
    compute_conservative_forces,
    huber_force_loss,
)

# Dynamic Batch Scaler & OOM Recovery
from Libraries.cochem_torq_dynamic_batch import (
    DynamicOOMRecovery,
    MolecularGraph,
    PackedMicroBatch,
    calculate_sparse_padding_waste,
    get_vram_telemetry,
    pack_graphs_dual_budget,
)

# C^2-Smooth Graph Pruning
from Libraries.cochem_torq_graph_pruning import (
    build_c2_reciprocal_graph,
    check_reciprocal_topology,
    compute_center_of_mass,
    compute_pairwise_conservative_forces,
    enforce_graph_reciprocity,
    evaluate_momentum_and_antisymmetry,
    quintic_c2_derivative,
    quintic_c2_second_derivative,
    quintic_c2_switching,
    verify_c2_continuity_boundary,
)

# Gradient Checkpointing
from Libraries.cochem_torq_gradient_checkpointing import (
    CheckpointedMLFF,
    compute_composite_loss,
    evaluate_forces_parity,
    profile_checkpointing_memory,
)

# ANI-2x Transfer Learning
from Libraries.cochem_torq_ani2x_transfer import (
    BASE_ANI2X_SPECIES,
    ANI2xModel,
    AtomicHead,
    expand_ani2x_domain,
    generate_test_ani2x_weights,
    get_llrd_parameter_groups,
    load_verified_ani2x_weights,
)

# TorchScript Export
from Libraries.cochem_torq_torchscript_export import (
    TorchScriptableMLFF,
    compile_and_validate_torchscript,
    compute_energy_and_forces_eager,
    export_model_to_torchscript,
    verify_torchscript_parity,
)

# Distributed Early Stopping
from Libraries.cochem_torq_distributed_early_stopping import (
    DistributedEarlyStopping,
    distributed_worker_routine,
    find_free_port,
)

# Loss Landscape Visualization
from Libraries.cochem_torq_loss_landscape import (
    compute_1d_loss_surface,
    compute_2d_loss_grid,
    generate_filter_normalized_direction,
    generate_orthogonal_filter_directions,
    render_loss_contour_plot,
    restore_base_weights,
    set_perturbed_weights,
)

# Dynamic Mixed-Precision Trainer
from Libraries.cochem_torq_amp_trainer import (
    AMPTrainer,
    resolve_amp_precision,
)

# Storage & Atomic Checkpointing
from Libraries.cochem_torq_training_persistence import (
    HDF5DatasetManager,
    configure_cluster_hdf5_environment,
    load_atomic_checkpoint,
    save_atomic_checkpoint,
    worker_init_fn,
)

# Inference Errors (Chunks 18, 19, 20)
from Libraries.cochem_torq_inference_errors import (
    ActiveLearningSelectionError,
    AirGapIntegrityError,
    AirGapViolationError,
    BaselineExecutionError,
    CalibrationSizeError,
    ClashDetectedError,
    ConcurrencyLockError,
    ConvergenceError,
    CutoffContinuityError,
    DispersionParameterError,
    EnsembleConsensusError,
    GradientExplosionError,
    HDF5DataModuleLockError,
    HardwareDispatchError,
    NumericalParityError,
    OpsetUnsupportedError,
    PBCGraphError,
    PhysicsDivergenceError,
    TorqInferenceError,
    VanishingGradientWarning,
)

# Inference Schemas (Chunks 18, 19, 20)
from Libraries.cochem_torq_inference_schemas import (
    ActiveLearningOrchestratorConfig,
    C2SmoothCutoffConfig,
    ChunkedHDF5DataModuleConfig,
    CommitteeEnsembleConfig,
    ConformalInterval,
    ConformalPredictorConfig,
    DeltaMLConfig,
    DispersionD3Config,
    FiniteDiffVerificationResult,
    GNNGradientDebuggerConfig,
    HPORunConfig,
    LBFGSOptimizationState,
    LBFGSOptimizerConfig,
    MultiTaskPrediction,
    NeighborListResult,
    ONNXExportSpec,
    PBCRadialGraphConfig,
    VibrationalModes,
)

# Multi-Task Learning Head (Chunk 20)
from Libraries.cochem_torq_multitask import (
    HomoscedasticMultiTaskLoss,
    MultiTaskHead,
    huber_loss,
)

# Finite-Difference Verification (Chunk 20)
from Libraries.cochem_torq_finite_difference import (
    verify_finite_difference_forces,
)

# Vibrational Frequency & Hessian Analysis (Chunk 20)
from Libraries.cochem_torq_vibrational import (
    CODATA_2022_FREQ_FACTOR,
    CODATA_2022_HC_EV_CM,
    CODATA_2022_KAPPA,
    analyze_vibrational_frequencies,
    compute_cartesian_hessian,
    compute_eckart_projector,
    resolve_ciaaw_monoisotopic_mass,
)

# TorchDynamo ONNX Export (Chunk 20)
from Libraries.cochem_torq_onnx_export import (
    DEFAULT_DYNAMIC_AXES,
    export_to_onnx,
    validate_onnx_spec,
    verify_onnx_parity,
)

# Environment & Hardware Concurrency (Chunk 20)
from Libraries.cochem_torq_environment import (
    EphemeralScratchSession,
    atomic_promote_to_store,
    dispatch_device_safely,
    resolve_hpc_safe_scratch,
)


# TORQ Molecular Dynamics Part 1 (Chunk 21)
from Libraries.cochem_torq_md_errors import (
    EnergyDriftExceededError,
    HardwareDispatchError as MDHardwareDispatchError,
    ReplicaExchangeDivergenceError,
    SymplecticIntegratorError,
    TorqMDError,
)
from Libraries.cochem_torq_md_schemas import (
    ExchangeLog,
    MDState,
    REMDConfig,
    TrajectoryFrame,
    VelocityVerletConfig,
)
from Libraries.cochem_torq_md_env import (
    dispatch_md_device,
    resolve_hpc_safe_scratch as resolve_md_scratch,
)
from Libraries.cochem_torq_symplectic import (
    BOLTZMANN_CONSTANT,
    ELEMENTARY_CHARGE,
    KAPPA_ACC,
    KAPPA_ACC_INV,
    UNIFIED_ATOMIC_MASS_KG,
    VelocityVerletIntegrator,
    compute_conservative_forces,
    compute_dimensional_acceleration,
    compute_instantaneous_temperature,
    compute_kinetic_energy,
    remove_center_of_mass_momentum,
)
from Libraries.cochem_torq_remd import (
    ReplicaExchangeEngine,
    ReplicaState,
    baoab_langevin_step,
    compute_geometric_temperature_schedule,
    evaluate_metropolis_swap,
    rescale_velocities_on_swap,
)
from Libraries.cochem_torq_trajectory import (
    HDF5TrajectoryReader,
    HDF5TrajectoryWriter,
)


# Active Learning (Chunk 18)
from Libraries.cochem_torq_active_learning import (
    ActiveLearningHDF5Manager,
    ActiveLearningOrchestrator,
    ActiveLearningState,
    CandidateGeometry,
    center_geometry_mass_weighted,
    check_stage_b_rotational_redundancy,
    compute_max_force_epistemic_std,
    compute_qbc_energy_variance,
    compute_rotational_constants,
    kabsch_rmsd,
    route_qm_tier,
)

# Chunked HDF5 DataModule (Chunk 18)
from Libraries.cochem_torq_hdf5_datamodule import (
    ChunkedHDF5DataModule,
    ChunkedHDF5Dataset,
    h5_worker_init_fn,
    jagged_graph_collate,
)

# Committee Ensemble (Chunk 18)
from Libraries.cochem_torq_committee_ensemble import (
    CommitteeEnsemble,
    CommitteePrediction,
    compute_committee_moments,
)

# C^2-Smooth Cutoff (Chunk 18)
from Libraries.cochem_torq_c2_cutoff import (
    C2SmoothCutoff,
    quintic_c2_envelope,
    quintic_c2_first_derivative,
    quintic_c2_second_derivative,
    quintic_c2_spatial_gradient,
    quintic_c2_spatial_hessian,
    verify_cutoff_continuity,
)

# GNN Gradient Health Debugger (Chunk 18)
from Libraries.cochem_torq_gnn_debugger import (
    GNNGradientDebugger,
)

# PBC Radial Graph & Virial Stress (Chunk 18)
from Libraries.cochem_torq_pbc_graph import (
    PBCGraph,
    PBCRadialGraphEngine,
    build_pbc_radial_graph,
    cartesian_to_fractional,
    compute_cell_volume,
    compute_hydrostatic_pressure,
    compute_interplanar_spacings,
    compute_virial_stress_tensor,
    fractional_to_cartesian,
)

# Hyperparameter Optimization Suite (Chunk 19)
from Libraries.cochem_torq_hpo import (
    ASHAPruner,
    BasePruner,
    HPOStudy,
    HPOTrial,
    MedianPruner,
    TrialPruned,
    compute_hpo_loss,
    create_hpo_study,
)

# Delta-Learning Architecture (Chunk 19)
from Libraries.cochem_torq_delta_ml import (
    BaselinePhysicsEngine,
    DeltaMLEngine,
    EMTBaselineEngine,
    GFN2xTBEngine,
    LennardJonesBaselineEngine,
    PM6Engine,
    UnitHarmonizer,
)

# Storage Architecture
from Libraries.cochem_torq_storage import (
    HDF5StorageManager,
    HDF5TorqStorage,
)

# Conformal Prediction Uncertainty (Chunk 19)
from Libraries.cochem_torq_conformal import (
    CalibrationSample,
    ConformalPredictor,
)

# L-BFGS Geometry Optimizer (Chunk 19)
from Libraries.cochem_torq_lbfgs_optimizer import (
    LBFGSOptimizer,
    check_clash,
    project_forces_eckart,
)

# Grimme D3 Empirical Dispersion (Chunk 19)
from Libraries.cochem_torq_dispersion_d3 import (
    CANONICAL_DISPERSION_SHA256,
    DispersionD3Layer,
    compute_coordination_numbers,
)

# Spatial Neighbor List Generator (Chunk 19)
from Libraries.cochem_torq_neighbor_list import (
    TRITON_AVAILABLE,
    build_neighbor_list,
)

__all__ = [
    # Errors
    "CoChemError",
    "CoChemTorqError",
    "TorqTrainingError",
    "HDF5LockTimeoutError",
    "PrecisionDivergenceError",
    "CheckpointCorruptionError",
    "DistributedSyncError",
    "UnsupportedElementError",
    "ParityVerificationError",
    "DiscontinuousForceError",
    "NonReciprocalGraphError",
    "OOMRecoveryError",
    "EquivarianceBreakError",
    "SchedulerDivergenceError",
    # Inference Errors (Chunks 18 & 19)
    "TorqInferenceError",
    "ActiveLearningSelectionError",
    "HDF5DataModuleLockError",
    "EnsembleConsensusError",
    "CutoffContinuityError",
    "GradientExplosionError",
    "VanishingGradientWarning",
    "PBCGraphError",
    "AirGapViolationError",
    "HardwareDispatchError",
    "AirGapIntegrityError",
    "ClashDetectedError",
    "ConvergenceError",
    "CalibrationSizeError",
    "BaselineExecutionError",
    "DispersionParameterError",
    # Schemas
    "TrainingDynamicsConfig",
    "TransferLearningConfig",
    "TorchScriptExportConfig",
    "DistributedEarlyStoppingConfig",
    "LossLandscapeConfig",
    "GNNWarmRestartSchedulerConfig",
    "ForceMatchingLossConfig",
    "DynamicBatchScalerConfig",
    "C2GraphPrunerConfig",
    # Inference Schemas (Chunks 18 & 19)
    "ActiveLearningOrchestratorConfig",
    "ChunkedHDF5DataModuleConfig",
    "CommitteeEnsembleConfig",
    "C2SmoothCutoffConfig",
    "GNNGradientDebuggerConfig",
    "PBCRadialGraphConfig",
    "HPORunConfig",
    "DeltaMLConfig",
    "ConformalPredictorConfig",
    "LBFGSOptimizerConfig",
    "DispersionD3Config",
    "NeighborListResult",
    "ConformalInterval",
    "LBFGSOptimizationState",
    # Masses
    "get_atomic_masses",
    "get_monoisotopic_mass",
    "get_monoisotopic_masses",
    "get_monoisotopic_masses_tensor",
    "resolve_ciaaw_monoisotopic_mass",
    # GNN Scheduler
    "GNNWarmRestartScheduler",
    "compute_lr_at_step",
    "check_and_clip_gradients",
    # Force Matching
    "ForceMatchingLoss",
    "compute_conservative_forces",
    "huber_force_loss",
    "compute_angular_cosine_similarity",
    # Dynamic Batching
    "MolecularGraph",
    "PackedMicroBatch",
    "pack_graphs_dual_budget",
    "calculate_sparse_padding_waste",
    "get_vram_telemetry",
    "DynamicOOMRecovery",
    # Graph Pruning
    "quintic_c2_switching",
    "quintic_c2_derivative",
    "quintic_c2_second_derivative",
    "verify_c2_continuity_boundary",
    "check_reciprocal_topology",
    "enforce_graph_reciprocity",
    "build_c2_reciprocal_graph",
    "compute_pairwise_conservative_forces",
    "evaluate_momentum_and_antisymmetry",
    "compute_center_of_mass",
    # Gradient Checkpointing
    "CheckpointedMLFF",
    "compute_composite_loss",
    "evaluate_forces_parity",
    "profile_checkpointing_memory",
    # ANI-2x Transfer
    "BASE_ANI2X_SPECIES",
    "ANI2xModel",
    "AtomicHead",
    "expand_ani2x_domain",
    "generate_test_ani2x_weights",
    "get_llrd_parameter_groups",
    "load_verified_ani2x_weights",
    # TorchScript Export
    "TorchScriptableMLFF",
    "compile_and_validate_torchscript",
    "compute_energy_and_forces_eager",
    "export_model_to_torchscript",
    "verify_torchscript_parity",
    # Distributed Early Stopping
    "DistributedEarlyStopping",
    "distributed_worker_routine",
    "find_free_port",
    # Loss Landscape
    "compute_1d_loss_surface",
    "compute_2d_loss_grid",
    "generate_filter_normalized_direction",
    "generate_orthogonal_filter_directions",
    "render_loss_contour_plot",
    "restore_base_weights",
    "set_perturbed_weights",
    # Mixed-Precision Trainer
    "AMPTrainer",
    "resolve_amp_precision",
    # Storage & Checkpoints
    "HDF5DatasetManager",
    "configure_cluster_hdf5_environment",
    "load_atomic_checkpoint",
    "save_atomic_checkpoint",
    "worker_init_fn",
    # Active Learning (Chunk 18)
    "ActiveLearningHDF5Manager",
    "ActiveLearningOrchestrator",
    "ActiveLearningState",
    "CandidateGeometry",
    "compute_qbc_energy_variance",
    "compute_max_force_epistemic_std",
    "center_geometry_mass_weighted",
    "compute_rotational_constants",
    "kabsch_rmsd",
    "check_stage_b_rotational_redundancy",
    "route_qm_tier",
    # Chunked HDF5 DataModule (Chunk 18)
    "ChunkedHDF5DataModule",
    "ChunkedHDF5Dataset",
    "h5_worker_init_fn",
    "jagged_graph_collate",
    # Committee Ensemble (Chunk 18)
    "CommitteeEnsemble",
    "CommitteePrediction",
    "compute_committee_moments",
    # C^2-Smooth Cutoff (Chunk 18)
    "C2SmoothCutoff",
    "quintic_c2_envelope",
    "quintic_c2_first_derivative",
    "quintic_c2_second_derivative",
    "quintic_c2_spatial_gradient",
    "quintic_c2_spatial_hessian",
    "verify_cutoff_continuity",
    # GNN Debugger (Chunk 18)
    "GNNGradientDebugger",
    # PBC Radial Graph (Chunk 18)
    "PBCGraph",
    "PBCRadialGraphEngine",
    "build_pbc_radial_graph",
    "cartesian_to_fractional",
    "fractional_to_cartesian",
    "compute_cell_volume",
    "compute_interplanar_spacings",
    "compute_virial_stress_tensor",
    "compute_hydrostatic_pressure",
    # Hyperparameter Optimization (Chunk 19)
    "ASHAPruner",
    "BasePruner",
    "HPOStudy",
    "HPOTrial",
    "MedianPruner",
    "TrialPruned",
    "compute_hpo_loss",
    "create_hpo_study",
    # Delta-Learning (Chunk 19)
    "BaselinePhysicsEngine",
    "DeltaMLEngine",
    "EMTBaselineEngine",
    "GFN2xTBEngine",
    "LennardJonesBaselineEngine",
    "PM6Engine",
    "UnitHarmonizer",
    # Conformal Prediction (Chunk 19)
    "CalibrationSample",
    "ConformalPredictor",
    # L-BFGS Optimizer (Chunk 19)
    "LBFGSOptimizer",
    "check_clash",
    "project_forces_eckart",
    # Grimme D3 Dispersion (Chunk 19)
    "CANONICAL_DISPERSION_SHA256",
    "DispersionD3Layer",
    "compute_coordination_numbers",
    # Spatial Neighbor List (Chunk 19)
    "TRITON_AVAILABLE",
    "build_neighbor_list",
    # Chunk 20: TORQ Inference, Vibrational, and Export
    "ConcurrencyLockError",
    "NumericalParityError",
    "OpsetUnsupportedError",
    "PhysicsDivergenceError",
    "FiniteDiffVerificationResult",
    "MultiTaskPrediction",
    "ONNXExportSpec",
    "VibrationalModes",
    "HomoscedasticMultiTaskLoss",
    "MultiTaskHead",
    "huber_loss",
    "verify_finite_difference_forces",
    "CODATA_2022_FREQ_FACTOR",
    "CODATA_2022_HC_EV_CM",
    "CODATA_2022_KAPPA",
    "analyze_vibrational_frequencies",
    "compute_cartesian_hessian",
    "compute_eckart_projector",
    "DEFAULT_DYNAMIC_AXES",
    "export_to_onnx",
    "validate_onnx_spec",
    "verify_onnx_parity",
    "dispatch_device_safely",
    "resolve_hpc_safe_scratch",
    "atomic_promote_to_store",
    "EphemeralScratchSession",

    # Chunk 21: TORQ Molecular Dynamics Part 1 (Symplectic & REMD)
    "TorqMDError",
    "EnergyDriftExceededError",
    "SymplecticIntegratorError",
    "ReplicaExchangeDivergenceError",
    "MDHardwareDispatchError",
    "VelocityVerletConfig",
    "REMDConfig",
    "MDState",
    "TrajectoryFrame",
    "ExchangeLog",
    "dispatch_md_device",
    "resolve_md_scratch",
    "KAPPA_ACC",
    "KAPPA_ACC_INV",
    "BOLTZMANN_CONSTANT",
    "ELEMENTARY_CHARGE",
    "UNIFIED_ATOMIC_MASS_KG",
    "compute_dimensional_acceleration",
    "remove_center_of_mass_momentum",
    "compute_kinetic_energy",
    "compute_instantaneous_temperature",
    "VelocityVerletIntegrator",
    "compute_geometric_temperature_schedule",
    "evaluate_metropolis_swap",
    "rescale_velocities_on_swap",
    "baoab_langevin_step",
    "ReplicaState",
    "ReplicaExchangeEngine",
    "HDF5TrajectoryWriter",
    "HDF5TrajectoryReader",
]


