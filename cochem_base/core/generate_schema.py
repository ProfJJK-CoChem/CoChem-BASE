import json
import logging
import os
from pathlib import Path

from cochem_base.core.models import MethodMatrixV4

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def generate_schema() -> None:
    schema = MethodMatrixV4.model_json_schema() if hasattr(MethodMatrixV4, "model_json_schema") else MethodMatrixV4.schema()
    
    artifacts_dir_env = os.getenv("COCHEM_ARTIFACTS_DIR")
    artifacts_dir = Path(artifacts_dir_env) if artifacts_dir_env else Path.home() / "cochem_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    schema_path = artifacts_dir / "method_matrix.json"
    
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=4)
    logger.info(f"Successfully generated v4 schema at {schema_path}")


if __name__ == "__main__":
    generate_schema()
