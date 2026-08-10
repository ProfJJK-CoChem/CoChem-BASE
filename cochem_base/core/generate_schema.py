import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from cochem_base.core.models import MethodMatrixV4

def generate_schema():
    schema = MethodMatrixV4.model_json_schema() if hasattr(MethodMatrixV4, "model_json_schema") else MethodMatrixV4.schema()
    schema_path = os.path.join(os.path.dirname(__file__), "method_matrix.json")
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=4)
    print(f"Successfully generated v4 schema at {schema_path}")

if __name__ == "__main__":
    generate_schema()
