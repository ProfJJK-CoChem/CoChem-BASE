import json
import os
from cochem_base.core.models import CorrelationMatrix

def generate_schema():
    schema = CorrelationMatrix.schema() if hasattr(CorrelationMatrix, "schema") else CorrelationMatrix.model_json_schema()
    
    schema_path = os.path.join(os.path.dirname(__file__), "method_matrix.json")
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=4)
        
    print(f"Successfully generated {schema_path}")

if __name__ == "__main__":
    generate_schema()
