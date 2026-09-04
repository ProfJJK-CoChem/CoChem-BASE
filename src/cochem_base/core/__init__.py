"""Authoritative Unified Core Namespace for CoChem Base.

Re-exports core registry, configuration, sandboxing, air-gap, file locking,
IPC serialization, HDF5 PES stores, and quantum chemistry schema/exception protocols.
"""

from __future__ import annotations

# 1. Authoritative registry manager and schemas
from cochem_base.core import cochem_core_registry_manager
from cochem_base.core.cochem_core_registry_manager import (
    AtomicFileLock,
    BaseMetadataServer,
    BasisSetNotFoundError,
    CoChemLockTimeoutError,
    FilesystemMetadataServer,
    MetadataBackendType,
    MetadataServerManager,
    PostgresMetadataServer,
    RecordNotFoundError,
    RedisMetadataServer,
    RegistryCorruptionError,
    RegistryError,
    RegistryLockError,
    RegistryLockTimeoutError,
    RegistryManager,
    RegistryMissingError,
    RegistryParseError,
    SchemaMigrationError,
    _sanitize_path_leakages,
    atomic_write_json,
    broadcast_system_config,
    default_metadata_manager,
    get_active_job,
    get_default_config_path,
    hash_environment,
    interpolate_env_vars,
    is_master_node,
    list_active_jobs,
    load_system_config,
    migrate_schema,
    nfs_atomic_directory_rename,
    receive_system_config_broadcast,
    register_active_job,
    remove_active_job,
    save_system_config,
    update_active_job,
    update_system_config,
)

# RegistryManager alias for unified core namespace
CoChemRegistry = RegistryManager

# 2. Configuration authority
# 4. Air-Gap Coordination
from cochem.core.airgap_coordinator import (
    AirGapConfig,
    AirGapCoordinator,
    AirGapViolationError,
    TripartiteAirGapCoordinator,
    TripartiteStorageConfig,
    get_tier_file_lock,
)

# 3. Sandboxing
from cochem.core.cochem_sandbox import (
    SandboxConfig,
    SandboxContext,
    SandboxExecutionError,
    SandboxSecurityViolationError,
)
from cochem.core.config import (
    CoChemConfigManager,
    CoChemRootConfig,
    ConfigurationParseError,
    CoreConfig,
    DatabaseConfig,
    OrchestrationConfig,
    QmMMConfig,
    TelemetryConfig,
    get_workspace_config,
)

# 5. Centralized File Locking
from cochem.core.context import FileLock

# 7. Ingestors, Schemas & Quantum Chemistry Domain Exceptions
from cochem.core.ingestors.protocols import (
    HessianSymmetryError,
    MolecularStructureData,
    QCResultsSchema,
    QCValidationError,
    SpinContaminationError,
)

# 6. IPC, Memory & PES Store
from cochem.core.ipc.serializer import (
    MAX_IPC_PAYLOAD_BYTES,
    HMACSocketClient,
    HMACSocketServer,
    IPCPayloadError,
    OversizedPayloadError,
    PESStore,
    SharedMemoryBuffer,
    TruncatedPayloadError,
    pack_payload,
    unpack_payload,
)

# 8. Mendeleev Mass Invariants
from cochem.core.mendeleev_invariants import MendeleevInvariantError

# 9. Stage-0 Facade Re-exports: HDF5 Manager, Models, Constants, PES Records
from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager
from cochem_base.core.cochem_crypto import (
    did_key_to_public_key,
    public_key_to_did_key,
    sign_report_payload,
    verify_report_payload,
)
from cochem_base.core.cochem_provenance import DAGNode, get_local_prov_context
from cochem_base.core.cochem_version import get_vcs_provenance
from cochem_base.core.exceptions import IsotopeStabilityError, RadiusNotFoundError
from cochem_base.core.glossary import CalculationFidelity, UnitConversionConstants
from cochem_base.core.licensing import OFFICIAL_SPDX_LICENSES, validate_spdx_license
from cochem_base.core.metadata import (
    collect_hardware_metadata,
    get_covalent_radius,
    get_isotopic_mass,
)
from cochem_base.core.models import (
    NAMESPACE_COCHEM,
    CalculationJobPayload,
    MolecularTopology,
    PESPointRecord,
    QCResultsRecord,
)
from cochem_base.core_engine.cochem_core_pes_store import (
    PESStore,
    get_node_local_scratch_dir,
)

__all__ = [
    # Registry
    "cochem_core_registry_manager",
    "AtomicFileLock",
    "BaseMetadataServer",
    "BasisSetNotFoundError",
    "CoChemLockTimeoutError",
    "FilesystemMetadataServer",
    "IsotopeStabilityError",
    "MetadataBackendType",
    "MetadataServerManager",
    "PostgresMetadataServer",
    "RecordNotFoundError",
    "RedisMetadataServer",
    "RegistryCorruptionError",
    "RegistryError",
    "RegistryLockError",
    "RegistryLockTimeoutError",
    "RegistryManager",
    "RegistryMissingError",
    "RegistryParseError",
    "SchemaMigrationError",
    "CoChemRegistry",
    "_sanitize_path_leakages",
    "atomic_write_json",
    "broadcast_system_config",
    "default_metadata_manager",
    "get_active_job",
    "get_default_config_path",
    "hash_environment",
    "interpolate_env_vars",
    "is_master_node",
    "list_active_jobs",
    "load_system_config",
    "migrate_schema",
    "nfs_atomic_directory_rename",
    "receive_system_config_broadcast",
    "register_active_job",
    "remove_active_job",
    "save_system_config",
    "update_active_job",
    "update_system_config",
    # Config
    "CoChemConfigManager",
    "CoChemRootConfig",
    "ConfigurationParseError",
    "CoreConfig",
    "DatabaseConfig",
    "OrchestrationConfig",
    "QmMMConfig",
    "TelemetryConfig",
    "get_workspace_config",
    # Sandbox
    "SandboxConfig",
    "SandboxContext",
    "SandboxExecutionError",
    "SandboxSecurityViolationError",
    # Airgap
    "AirGapConfig",
    "AirGapCoordinator",
    "AirGapViolationError",
    "TripartiteAirGapCoordinator",
    "TripartiteStorageConfig",
    "get_tier_file_lock",
    # Context & Locking
    "FileLock",
    # IPC & PES
    "HMACSocketClient",
    "HMACSocketServer",
    "IPCPayloadError",
    "MAX_IPC_PAYLOAD_BYTES",
    "OversizedPayloadError",
    "PESStore",
    "SharedMemoryBuffer",
    "TruncatedPayloadError",
    "pack_payload",
    "unpack_payload",
    # Protocols & Physics Exceptions
    "HessianSymmetryError",
    "MolecularStructureData",
    "QCResultsSchema",
    "QCValidationError",
    "SpinContaminationError",
    # Mendeleev Invariants
    "MendeleevInvariantError",
    # Stage-0 Facade Deliverables
    "CoChemHDF5Manager",
    "QCResultsRecord",
    "MolecularTopology",
    "PESPointRecord",
    "UnitConversionConstants",
    # Chunk 6 Deliverables
    "IsotopeStabilityError",
    "RadiusNotFoundError",
    "OFFICIAL_SPDX_LICENSES",
    "validate_spdx_license",
    "get_isotopic_mass",
    "get_covalent_radius",
    "collect_hardware_metadata",
    "DAGNode",
    "get_local_prov_context",
    "did_key_to_public_key",
    "public_key_to_did_key",
    "sign_report_payload",
    "verify_report_payload",
    "get_vcs_provenance",
    "CalculationFidelity",
    "CalculationJobPayload",
    "NAMESPACE_COCHEM",
    "get_node_local_scratch_dir",
]
