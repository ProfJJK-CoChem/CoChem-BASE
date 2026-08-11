import os
import sys
import logging
from typing import Tuple, Optional
from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestEnvironment")


def check_cochem_base_silo() -> Tuple[bool, str]:
    """Checks if the python execution environment is cochem_base_silo."""
    env_name = os.environ.get("CONDA_DEFAULT_ENV", "")
    if "cochem_base_silo" in env_name or "cochem_base_silo" in sys.executable:
        return True, "Success: Running within cochem_base_silo."
    return False, f"Warning: Not running within cochem_base_silo (current env: {env_name})."


def check_artifacts_dir(path: Optional[str] = None) -> Tuple[bool, str]:
    """Checks if the CoChem_Artifacts directory exists."""
    if path is None:
        path = str(get_artifact_dir())

    if os.path.exists(path) and os.path.isdir(path):
        return True, f"Success: CoChem_Artifacts directory found at {path}."
    return False, f"Error: CoChem_Artifacts directory missing at {path}."


if __name__ == "__main__":
    logger.info(check_cochem_base_silo()[1])
    logger.info(check_artifacts_dir()[1])
