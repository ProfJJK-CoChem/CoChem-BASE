"""CoChem-BASE core package."""

from .config_loader import (
    get_artifact_dir,
    get_base_root,
    get_cochem_root,
    get_cochem_scratch,
    get_default_cochem_config,
    get_modules_dir,
    get_mps_directories,
    get_ramdisk_dir,
    get_repo_root,
    get_runtime_dir,
    get_scratch_dir,
    get_state_file_path,
    get_telemetry_socket_path,
    get_telemetry_transport,
    get_telemetry_udp_address,
    load_system_config,
    load_system_config_dict,
    prepend_executable_directory,
    resolve_conda_executable,
    resolve_config_path,
    resolve_executable,
    resolve_mapped_path,
    resolve_wsl_executable,
    update_config,
)

_SUBMODULES = {
    "cochem_catalog_compiler",
    "cochem_h5_healer",
    "cochem_jax_builder",
    "cochem_spcat_bridge",
    "cochem_tensor_extractor",
    "cochem_torq_alignment",
    "cochem_torq_engine",
    "cochem_torq_export",
    "cochem_torq_init",
    "cochem_torq_mace",
    "cochem_torq_quench",
    "cochem_torq_schema",
    "cochem_torq_slicer",
    "cochem_torq_telemetry",
    "cochem_torq_topology",
    "cochem_torq_vault",
    "cochem_torq_watchdog",
}


def __getattr__(name: str):
    if name in _SUBMODULES:
        import importlib
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__version__ = "0.1.0"

__all__ = [
    "__version__",
    "get_artifact_dir",
    "get_base_root",
    "get_cochem_root",
    "get_cochem_scratch",
    "get_default_cochem_config",
    "get_modules_dir",
    "get_mps_directories",
    "get_ramdisk_dir",
    "get_repo_root",
    "get_runtime_dir",
    "get_scratch_dir",
    "get_state_file_path",
    "get_telemetry_socket_path",
    "get_telemetry_transport",
    "get_telemetry_udp_address",
    "load_system_config",
    "load_system_config_dict",
    "prepend_executable_directory",
    "resolve_conda_executable",
    "resolve_config_path",
    "resolve_executable",
    "resolve_mapped_path",
    "resolve_wsl_executable",
    "update_config",
    "cochem_tensor_extractor",
    "cochem_jax_builder",
    "cochem_spcat_bridge",
    "cochem_torq_export",
    "cochem_torq_telemetry",
    "cochem_catalog_compiler",
    "cochem_h5_healer",
    "cochem_torq_init",
    "cochem_torq_schema",
    "cochem_torq_vault",
    "cochem_torq_topology",
    "cochem_torq_alignment",
    "cochem_torq_mace",
    "cochem_torq_quench",
    "cochem_torq_slicer",
    "cochem_torq_engine",
    "cochem_torq_watchdog",
]
