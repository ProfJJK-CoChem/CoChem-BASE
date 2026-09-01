#!/usr/bin/env python3
"""
CoChem-BASE Setup Stage 5: Config Finalizer with Pydantic Schema Validation.
Validates cochem_system_config.json against CoChemConfig Pydantic model.
Adheres to the Root Cause Resolution Mandate by enforcing strict upstream schema compliance.
"""

import json
import logging
from pathlib import Path

from cochem_base.config_loader import resolve_config_path
from core_engine.cochem_core_registry_schema import CoChemConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def load_and_validate_config(config_path: Path) -> CoChemConfig:
    """Loads and validates cochem_system_config.json using CoChemConfig."""
    if not config_path.exists():
        logger.error(f"[MISSING DATA] Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Enforce strict validation to reject upstream data anomalies rather than healing them.
    return CoChemConfig.model_validate(raw_data, strict=True)


def finalize_system_config(config_path: Path) -> CoChemConfig:
    """Final stage handler to ensure system configuration is valid and persisted."""
    return load_and_validate_config(config_path)


if __name__ == "__main__":
    import sys
    cfg_file = Path(sys.argv[1]) if len(sys.argv) > 1 else resolve_config_path()
    if cfg_file.exists():
        cfg = finalize_system_config(cfg_file)
        logger.info(f"Successfully finalized config: {cfg_file}")
    else:
        logger.error(f"[MISSING DATA] Configuration file not found: {cfg_file}")
