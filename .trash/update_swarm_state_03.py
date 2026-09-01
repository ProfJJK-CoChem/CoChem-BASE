import json
from datetime import datetime
import os

file_path = "D:/__CoChem/GitHub-Repo/CoChem-BASE/swarm_state.json"
try:
    with open(file_path, "r") as f:
        data = json.load(f)
except Exception:
    data = {}

data["cochem-cell-03-silo-setup-keep"] = {
    "agent": "cochem-tester",
    "status": "SUCCESS",
    "artifacts": [
        "D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_silo_setup_keep_codespaces_mac.py"
    ],
    "timestamp": datetime.now().isoformat(),
    "message": "Test written and passed. Test logic contains EXPLICIT RETRY LOGIC, SERIALIZED EXECUTION, monkeypatching, tightened exception deflections, verified logger taking precedence, and a proper psutil sweeper inside a pytest fixture to clean up zombie conda processes."
}

with open(file_path, "w") as f:
    json.dump(data, f, indent=4)
print("Updated swarm_state.json for cochem-cell-03-silo-setup-keep")
