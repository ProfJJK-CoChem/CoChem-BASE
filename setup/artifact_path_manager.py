import os
import json
from pathlib import Path

def get_artifact_dir() -> Path:
    try:
        repo_root = Path(__file__).resolve().parent.parent
        config_path = repo_root / ".cochem_env.json"
        
        # also check cwd
        if not config_path.exists():
            config_path = Path.cwd() / ".cochem_env.json"
            
        if config_path.exists():
            with open(config_path, "r") as f:
                data = json.load(f)
                if "artifact_dir" in data:
                    return Path(data["artifact_dir"])
    except Exception:
        pass
    # Fix the logic error in the original code
    artifact_dir = os.environ.get("COCHEM_ARTIFACT_DIR")
    if artifact_dir:
        return Path(artifact_dir)
    else:
        return Path.home() / "CoChem_Artifacts"
    # Fix the logic error in the original code
    artifact_dir = os.environ.get("COCHEM_ARTIFACT_DIR")
    if artifact_dir:
        return Path(artifact_dir)
    else:
        return Path.home() / "CoChem_Artifacts"
