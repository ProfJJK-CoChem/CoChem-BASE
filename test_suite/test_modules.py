import os
from pathlib import Path

def check_modules_installed(base_path=None):
    """Checks if the required modules are present in the modules directory."""
    if base_path is None:
        base_path = os.environ.get("COCHEM_MODULE_DIR")
        if not base_path:
            root = Path(__file__).resolve().parents[2]
            if (root / "CoChem-BASE").exists():
                base_path = str(root)
            else:
                base_path = str(Path.home() / "CoChem_Artifacts" / "modules")

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
    print(check_modules_installed()[1])
