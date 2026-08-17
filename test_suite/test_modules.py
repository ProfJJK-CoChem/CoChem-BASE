import logging
import sys
from pathlib import Path

from cochem_base.config_loader import get_modules_dir, resolve_mapped_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestModules")


def check_modules_installed(base_path: str | Path | None = None) -> tuple[bool, str]:
    """Checks if the required modules are present in the modules directory."""
    modules_dir: Path = resolve_mapped_path(base_path, get_modules_dir()) if base_path else get_modules_dir()

    required_modules: list[str] = ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"]
    missing: list[str] = []
    found: list[str] = []

    for mod in required_modules:
        mod_path: Path = modules_dir / mod
        if mod_path.exists() and mod_path.is_dir():
            found.append(mod)
        else:
            missing.append(mod)

    if missing:
        return False, f"Error: Missing modules in {modules_dir}: {', '.join(missing)}"
    return True, f"Success: All required modules found in {modules_dir}."


if __name__ == "__main__":
    success, message = check_modules_installed()
    if not success:
        logger.error(message)
        sys.exit(1)
    
    logger.info(message)
