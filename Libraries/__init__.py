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
    DistributedSyncError,
    HDF5LockTimeoutError,
    ParityVerificationError,
    PrecisionDivergenceError,
    TorqTrainingError,
    UnsupportedElementError,
)

# Pydantic v2 Schemas
from Libraries.cochem_torq_training_schemas import (
    DistributedEarlyStoppingConfig,
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
    # Schemas
    "TrainingDynamicsConfig",
    "TransferLearningConfig",
    "TorchScriptExportConfig",
    "DistributedEarlyStoppingConfig",
    "LossLandscapeConfig",
    # Masses
    "get_monoisotopic_mass",
    "get_monoisotopic_masses",
    "get_monoisotopic_masses_tensor",
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
