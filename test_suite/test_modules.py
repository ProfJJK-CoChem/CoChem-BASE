import os
from pathlib import Path

def check_modules_installed(base_path=r"D:\_CoChem\CoChem_Artifacts\modules"):
    """Checks if the required modules are present in the modules directory."""
    required_modules = ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ", "CoChem-SCRIBE"]
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
