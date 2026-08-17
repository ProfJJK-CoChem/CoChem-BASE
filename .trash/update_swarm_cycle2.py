import json

path = r"D:\__CoChem\GitHub-Repo\CoChem-BASE\swarm_state.json"
with open(path, "r") as f:
    data = json.load(f)

data["cochem-improve-torq-hessian-cycle2"] = {
    "agent": "cochem-improve",
    "status": "PASSED_WITH_RESERVATIONS",
    "error_codes": ["ERR_SYNTAX_HALLUCINATION"],
    "timestamp": "2026-08-17T03:02:00Z",
    "message": "Scale routing and NumFreq fallback approved. Syntax hallucination (.rwf, KeepWFN, partial .hess) corrected to use ORCA's native .res.%5d.Type files and %freq Restart true end."
}

with open(path, "w") as f:
    json.dump(data, f, indent=2)
