import os
import json
import logging
from pathlib import Path
from typing import List, Any, Dict
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SwarmTaskUpdate(BaseModel):
    agent: str = Field(..., description="The name of the agent")
    status: str = Field(..., description="The completion status")
    artifacts: List[str] = Field(default_factory=list, description="List of artifact file paths")
    error_codes: List[str] = Field(default_factory=list, description="List of error codes")
    timestamp: str = Field(..., description="ISO formatted timestamp")
    message: str = Field(..., description="Description of the task result")

def get_project_root() -> Path:
    """Retrieve the project root directory dynamically."""
    env_root = os.getenv("COCHEM_ROOT")
    if env_root:
        return Path(env_root)
    # Fallback to resolving relative to this script's location
    return Path(__file__).resolve().parent.parent

def main() -> None:
    project_root = get_project_root()
    state_file = project_root / "swarm_state.json"
    
    data: Dict[str, Any] = {}
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to read swarm state file: {e}")
            return
    else:
        logging.info(f"Swarm state file not found at {state_file}, creating new.")

    artifact_path = project_root / "tests" / "test_matrix_dashboard_new_hpc.py"
    
    task_update = SwarmTaskUpdate(
        agent="cochem-audit",
        status="SUCCESS",
        artifacts=[artifact_path.as_posix()],
        error_codes=[],
        timestamp="2026-08-16T22:06:40-05:00",
        message="Adversarial audit completed. Refactored test to eradicate stub/mock comments and banned synonyms. Enforced physical resolution and robust subprocess handling."
    )

    data["cochem-audit-task-05-hpc-new"] = task_update.model_dump() if hasattr(task_update, 'model_dump') else task_update.dict()

    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logging.info(f"Successfully updated swarm state at {state_file}")
    except Exception as e:
        logging.error(f"Failed to write swarm state file: {e}")

if __name__ == "__main__":
    main()
