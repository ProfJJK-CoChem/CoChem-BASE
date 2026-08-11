import json
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from cochem_base.core.models import MethodMatrixV4


def generate_schema() -> None:
    schema = MethodMatrixV4.model_json_schema() if hasattr(MethodMatrixV4, "model_json_schema") else MethodMatrixV4.schema()
    schema_path = os.path.join(os.path.dirname(__file__), "method_matrix.json")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=4)
    logger.info(f"Successfully generated v4 schema at {schema_path}")


if __name__ == "__main__":
    generate_schema()
