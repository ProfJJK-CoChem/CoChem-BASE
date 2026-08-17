import logging
from typing import Optional, Tuple

from cochem_base.config_loader import get_modules_dir, resolve_mapped_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestModules")


def check_modules_installed(base_path: Optional[str] = None) -> Tuple[bool, str]:
    """Checks if the required modules are present in the modules directory."""
    modules_dir = resolve_mapped_path(base_path, get_modules_dir()) if base_path else get_modules_dir()

    required_modules = ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"]
    missing = []
    found = []

    for mod in required_modules:
        mod_path = modules_dir / mod
        if mod_path.exists() and mod_path.is_dir():
            found.append(mod)
        else:
            missing.append(mod)

    if missing:
        return False, f"Error: Missing modules in {modules_dir}: {', '.join(missing)}"
    return True, f"Success: All required modules found in {modules_dir}."


if __name__ == "__main__":
    logger.info(check_modules_installed()[1])
