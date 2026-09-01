#!/usr/bin/env python3
"""CoChem-BASE: Root-level backward compatibility alias for cochem_base.core.cochem_core_hdf5_manager.

Re-exports authoritative implementation for distributed IPC and single-master HDF5 data architecture.
"""

from __future__ import annotations

from cochem_base.core.cochem_core_hdf5_manager import (
    BasinRecord,
    CoChemHDF5Manager,
    DatasetNotFoundError,
    HDF5FilterViolationError,
    HDF5ManagerError,
    HDF5OntologyEnforcer,
    IPCRuntimeError,
    MasterDataAggregator,
    MasterWriteGatekeeper,
    NonMasterWriteRejectionError,
    QCSchemaAtomicResult,
    QCSchemaDriver,
    QCSchemaModel,
    QCSchemaMolecule,
    QCSchemaOptimizationResult,
    QCSchemaProperties,
    QCSchemaValidationError,
    QCSchemaWavefunction,
    SQLiteWALQueue,
    ZMQRealTimeStreamer,
    is_master_node,
    resolve_landscape_h5_path,
    sanitize_for_host_ram,
    strip_tensor_to_numpy,
    verify_dataset_filters,
    verify_no_swmr_usage,
    write_dataset_filtered,
)

__all__ = [
    "BasinRecord",
    "CoChemHDF5Manager",
    "DatasetNotFoundError",
    "HDF5FilterViolationError",
    "HDF5ManagerError",
    "HDF5OntologyEnforcer",
    "IPCRuntimeError",
    "MasterDataAggregator",
    "MasterWriteGatekeeper",
    "NonMasterWriteRejectionError",
    "QCSchemaAtomicResult",
    "QCSchemaDriver",
    "QCSchemaModel",
    "QCSchemaMolecule",
    "QCSchemaOptimizationResult",
    "QCSchemaProperties",
    "QCSchemaValidationError",
    "QCSchemaWavefunction",
    "SQLiteWALQueue",
    "ZMQRealTimeStreamer",
    "is_master_node",
    "resolve_landscape_h5_path",
    "sanitize_for_host_ram",
    "strip_tensor_to_numpy",
    "verify_dataset_filters",
    "verify_no_swmr_usage",
    "write_dataset_filtered",
]
