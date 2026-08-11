#!/usr/bin/env python3
"""
CoChem-BASE Setup Stage 5: Config Finalizer with Pydantic Schema Validation.
Validates cochem_system_config.json against CoChemConfig Pydantic model
and auto-heals configuration files.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any
from pydantic import ValidationError
from core_engine.cochem_core_registry_schema import CoChemConfig
from cochem_base.config_loader import resolve_config_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def auto_heal_config_dict(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Coerces invalid data types (e.g. string booleans) to schema compliant types."""
    if "hardware" in raw_data and isinstance(raw_data["hardware"], dict):
        hw = raw_data["hardware"]
        if "avx512_support" in hw and isinstance(hw["avx512_support"], str):
            hw["avx512_support"] = hw["avx512_support"].lower() in ("true", "1", "yes")
        if "subnormal_precision_trap" in hw and isinstance(hw["subnormal_precision_trap"], str):
            hw["subnormal_precision_trap"] = hw["subnormal_precision_trap"].lower() in ("true", "1", "yes")
    return raw_data


def load_and_validate_config(config_path: Path) -> CoChemConfig:
    """Loads and validates cochem_system_config.json using CoChemConfig."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_data = json.loads(f.read())

    try:
        return CoChemConfig.model_validate(raw_data)
    except ValidationError as ve:
        logger.warning(f"Config validation failed for {config_path}: {ve}. Auto-healing schema...")
        healed_data = auto_heal_config_dict(raw_data)
        healed_cfg = CoChemConfig.model_validate(healed_data)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(healed_cfg.model_dump_json(indent=2))
        return healed_cfg


def finalize_system_config(config_path: Path) -> CoChemConfig:
    """Final stage handler to ensure system configuration is valid and persisted."""
    return load_and_validate_config(config_path)


if __name__ == "__main__":
    import sys
    cfg_file = Path(sys.argv[1]) if len(sys.argv) > 1 else resolve_config_path()
    if cfg_file.exists():
        cfg = finalize_system_config(cfg_file)
        logger.info(f"Successfully finalized config: {cfg_file}")
