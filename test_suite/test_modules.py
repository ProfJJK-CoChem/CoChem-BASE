import os
import logging
from pathlib import Path
from typing import Tuple, Optional
from cochem_base.config_loader import get_artifact_dir, get_repo_root

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestModules")


def check_modules_installed(base_path: Optional[str] = None) -> Tuple[bool, str]:
    """Checks if the required modules are present in the modules directory."""
    if base_path is None:
        base_path = os.environ.get("COCHEM_MODULE_DIR")
        if not base_path:
            repo_root = get_repo_root()
            if (repo_root / "CoChem-BASE").exists():
                base_path = str(repo_root)
            else:
                base_path = str(get_artifact_dir() / "Registry" / "Modules")

    required_modules = ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"]
    missing = []
    found = []

    for mod in required_modules:
        mod_path = Path(base_path) / mod
        if mod_path.exists() and mod_path.is_dir():
            found.append(mod)
        else:
            missing.append(mod)

    if missing:
        return False, f"Error: Missing modules in {base_path}: {', '.join(missing)}"
    return True, f"Success: All required modules found in {base_path}."


if __name__ == "__main__":
    logger.info(check_modules_installed()[1])
