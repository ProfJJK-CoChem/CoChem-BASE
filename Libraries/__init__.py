"""CoChem-TORQ Training Dynamics, Transfer Learning, and Production Compilation Suite.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
"""

from __future__ import annotations

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
    get_monoisotopic_mass,
    get_monoisotopic_masses,
    get_monoisotopic_masses_tensor,
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
    # Masses
    "get_monoisotopic_mass",
    "get_monoisotopic_masses",
    "get_monoisotopic_masses_tensor",
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
]

