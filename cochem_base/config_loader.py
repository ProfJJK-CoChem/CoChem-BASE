#!/usr/bin/env python3
"""
CoChem-BASE Central Dynamic Configuration & Path Loader.
Provides authoritative, Pydantic-validated access to cochem_system_config.json
and dynamic workspace paths following the 4-tier resolution hierarchy.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from core_engine.cochem_core_registry_schema import CoChemConfig

logger = logging.getLogger(__name__)


def get_repo_root() -> Path:
    """Dynamically resolves the repository root directory."""
    # Anchored relative to this file: CoChem-BASE/cochem_base/config_loader.py -> repo root
    return Path(__file__).resolve().parent.parent.parent


def get_default_cochem_config() -> CoChemConfig:
    """Returns the fallback default CoChemConfig model instance."""
    return CoChemConfig(
        hardware={
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 16.0,
            "avx512_support": False,
            "gpu_profile": "None",
            "vram_gb": 0.0,
            "subnormal_precision_trap": False,
            "os_target": "windows_x86_64"
        },
        engines={
            "orca": {"status": "missing", "path": None, "version": None, "hash": None},
            "mpirun": {"status": "missing", "path": None, "version": None, "hash": None},
            "xtb": {"status": "missing", "path": None, "version": None, "hash": None}
        },
        silos={"torq_silo_active": False, "gpu_silo_active": False}
    )


def resolve_config_path(custom_path: Optional[Path] = None) -> Path:
    """
    Resolves cochem_system_config.json path via 4-tier resolution hierarchy:
    Tier 1: Explicit Parameter (Function/CLI Argument)
    Tier 2: Environment Variables (COCHEM_CONFIG, COCHEM_ARTIFACT_DIR)
    Tier 3: Central System Config (cochem_system_config.json in repo root or CoChem-BASE)
    Tier 4: Dynamic Workspace Discovery (Anchored relative to repo root)
    """
    if custom_path is not None:
        return Path(custom_path)

    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg and Path(env_cfg).exists():
        return Path(env_cfg)

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        art_cfg = Path(env_art) / "cochem_system_config.json"
        if art_cfg.exists():
            return art_cfg

    repo_cfg = get_repo_root() / "cochem_system_config.json"
    if repo_cfg.exists():
        return repo_cfg

    base_cfg = get_repo_root() / "CoChem-BASE" / "cochem_system_config.json"
    if base_cfg.exists():
        return base_cfg

    # Fallback to creating/defaulting inside repo root
    return repo_cfg


def load_system_config(config_path: Optional[Path] = None) -> CoChemConfig:
    """Loads and validates cochem_system_config.json into a CoChemConfig Pydantic model."""
    target_path = resolve_config_path(config_path)
    if not target_path.exists():
        logger.warning(f"Configuration file not found at {target_path}. Instantiating default CoChemConfig.")
        return get_default_cochem_config()

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw_data = json.loads(f.read())
    except (json.JSONDecodeError, ValueError, OSError) as e:
        logger.warning(f"Failed to read or parse JSON config at {target_path}: {e}. Instantiating default CoChemConfig.")
        return get_default_cochem_config()

    try:
        return CoChemConfig.model_validate(raw_data)
    except Exception as e:
        logger.warning(f"Config schema validation error for {target_path}: {e}. Instantiating default CoChemConfig.")
        return get_default_cochem_config()


def load_system_config_dict(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads validated system configuration as a dictionary."""
    cfg = load_system_config(config_path)
    return cfg.model_dump()


def get_artifact_dir() -> Path:
    """Dynamically resolves artifact workspace directory."""
    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return Path(env_art)
    
    repo_artifacts = get_repo_root() / ".agent_artifacts"
    if repo_artifacts.exists():
        return repo_artifacts

    home_artifacts = Path.home() / "CoChem_Artifacts"
    return home_artifacts
