import json
import datetime

state_file = r"D:\__CoChem\GitHub-Repo\CoChem-BASE\swarm_state.json"
with open(state_file, "r") as f:
    state = json.load(f)

state["agent_name"] = "cochem-audit"
state["status"] = "SUCCESS"
state["artifacts"] = [
    r"D:\__CoChem\GitHub-Repo\CoChem-BASE\calc\cochem_calc_input_generator.py",
    r"D:\__CoChem\GitHub-Repo\CoChem-BASE\calc\cochem_calc_output_parser.py"
]
state["error_codes"] = []
state["timestamp"] = datetime.datetime.now().isoformat()

with open(state_file, "w") as f:
    json.dump(state, f, indent=4)
