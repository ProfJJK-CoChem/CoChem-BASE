import os
import sys

def check_cochem_base_silo():
    """Checks if the python execution environment is cochem_base_silo."""
    # This is a naive check. A better approach might involve inspecting the CONDA_DEFAULT_ENV
    env_name = os.environ.get("CONDA_DEFAULT_ENV", "")
    if "cochem_base_silo" in env_name or "cochem_base_silo" in sys.executable:
        return True, "Success: Running within cochem_base_silo."
    return False, f"Warning: Not running within cochem_base_silo (current env: {env_name})."

def check_artifacts_dir(path=None):
    """Checks if the CoChem_Artifacts directory exists."""
    if path is None:
        path = os.environ.get("COCHEM_ARTIFACT_DIR", os.path.join(os.path.expanduser("~"), "CoChem_Artifacts"))
    
    if os.path.exists(path) and os.path.isdir(path):
        return True, f"Success: CoChem_Artifacts directory found at {path}."
    return False, f"Error: CoChem_Artifacts directory missing at {path}."

if __name__ == "__main__":
    print(check_cochem_base_silo()[1])
    print(check_artifacts_dir()[1])
