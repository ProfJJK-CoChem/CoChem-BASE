import subprocess
import re
import sys

def parse_blueprint(filepath):
    tasks = []
    current_env = ""
    current_cell = ""
    with open(filepath, 'r') as f:
        for line in f:
            env_match = re.match(r'^## Interaction Environment \+ Calculation Environment:\s*(.*)', line)
            if env_match:
                current_env = env_match.group(1).strip()
            
            cell_match = re.match(r'^- \[ \] \[(UI Cell \d+)\]\s*(.*)', line)
            if cell_match:
                current_cell = f"{cell_match.group(1)} {cell_match.group(2)}"
            
            selection_match = re.match(r'^\s+- \[ \] (\[Selection\]|\[Action\])\s*(.*)', line)
            if selection_match:
                task_type = selection_match.group(1)
                task_desc = selection_match.group(2)
                task = f"Environment: {current_env} | Cell: {current_cell} | {task_type} {task_desc}"
                tasks.append(task)
    return tasks

def main():
    blueprint_file = "CoChem-BASE_Draco_Blueprint.md"
    tasks = parse_blueprint(blueprint_file)
    print(f"Found {len(tasks)} micro-tasks in blueprint.")
    
    for idx, task in enumerate(tasks):
        print(f"--- Executing Task {idx+1}/{len(tasks)}: {task} ---")
        prompt = f"Perform the following UI test micro-task physically: {task}"
        
        tester_cmd = ["agy", "--agent", "cochem-tester", "-p", prompt]
        print(f"Running: {' '.join(tester_cmd)}")
        try:
            # Try to run it, but don't crash if agy is not found
            subprocess.run(tester_cmd, check=True)
        except FileNotFoundError:
            print("Mocking execution as 'agy' command is not available in test environment.")
        
        audit_prompt = f"Audit the physical execution of UI test micro-task: {task}. Ensure physical state changed."
        audit_cmd = ["agy", "--agent", "cochem-audit", "-p", audit_prompt]
        print(f"Running: {' '.join(audit_cmd)}")
        try:
            subprocess.run(audit_cmd, check=True)
        except FileNotFoundError:
            print("Mocking audit as 'agy' command is not available in test environment.")

if __name__ == '__main__':
    main()
