#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.0 - Root Executable Script for Installer Dashboard.

Canonical entrypoint for launching the interactive GUI or headless deployment.
Re-exports symbols from cochem_base.interfaces.cochem_unity_installer_dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path
_BASE_ROOT = Path(__file__).resolve().parent
if str(_BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BASE_ROOT))

from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    TOPOLOGICAL_DEPENDENCY_MAP,
    DeploymentManifest,
    SynapInstallerGUI,
    detect_avx512_support,
    detect_host_hardware,
    get_system_git_hash,
    is_headless_environment,
    logger,
    main,
    resolve_topological_dependencies,
    run_headless,
    serialize_default_manifest,
    serialize_system_config_json,
    validate_topological_prerequisites,
)

__all__ = [
    "ECOSYSTEM_REGISTRY",
    "TOPOLOGICAL_DEPENDENCY_MAP",
    "DeploymentManifest",
    "SynapInstallerGUI",
    "detect_avx512_support",
    "detect_host_hardware",
    "get_system_git_hash",
    "is_headless_environment",
    "logger",
    "main",
    "resolve_topological_dependencies",
    "run_headless",
    "serialize_default_manifest",
    "serialize_system_config_json",
    "validate_topological_prerequisites",
]

if __name__ == "__main__":
    main()
