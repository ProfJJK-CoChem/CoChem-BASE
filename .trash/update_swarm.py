import json

path = r"D:\__CoChem\GitHub-Repo\CoChem-BASE\swarm_state.json"
with open(path, "r") as f:
    data = json.load(f)

data["cochem-improve-torq-hessian"] = {
    "agent": "cochem-improve",
    "status": "REJECTED",
    "error_codes": ["ERR_METHOD_MATRIX_VIOLATION"],
    "timestamp": "2026-08-16T22:01:00-05:00",
    "message": "Suggestion rejected due to violation of Method Matrix v4 §8B.6 (ORCA analytical Hessians are non-restartable)."
}

with open(path, "w") as f:
    json.dump(data, f, indent=2)
