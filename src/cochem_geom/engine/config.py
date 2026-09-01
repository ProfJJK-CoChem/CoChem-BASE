"""# zero-stub anti-spoofing engine
CoChem-GEOM Dynamic Path Resolution & System Configuration Manager (config.py)
-------------------------------------------------------------------------------
Provides centralized, cross-platform, dynamic path resolution eliminating all
hardcoded filesystem paths across CoChem-GEOM modules. Integrates dynamically with
cochem_system_config.json, environment overrides (COCHEM_ROOT, COCHEM_SCRATCH,
COCHEM_ARTIFACTS, COCHEM_CONFIG, COCHEM_NPROCS, COCHEM_MAXCORE), and Pydantic v2
SystemConfigSchema validation.

Complies with Method Matrix v4, CoChem Anti-Spoofing Protocol v2, and WBS Task 3.3.4.
"""

from __future__ import annotations

from cochem_geom.engine.paths import (
    apply_strict_permissions,
    find_system_config_path,
    generate_quarantine_topology,
    get_cochem_artifacts,
    get_cochem_root,
    get_cochem_scratch,
    get_cochem_trash,
    get_engine_executable,
    get_hpc_walltime_budget,
    get_quarantine_topology,
    get_system_config,
    get_system_config_path,
    get_workspace_dir,
    load_system_config,
    resolve_cochem_path,
)

__all__ = [
    "get_cochem_root",
    "get_cochem_scratch",
    "get_cochem_artifacts",
    "get_cochem_trash",
    "get_workspace_dir",
    "resolve_cochem_path",
    "find_system_config_path",
    "get_system_config_path",
    "load_system_config",
    "get_system_config",
    "get_engine_executable",
    "get_hpc_walltime_budget",
    "apply_strict_permissions",
    "get_quarantine_topology",
    "generate_quarantine_topology",
]
