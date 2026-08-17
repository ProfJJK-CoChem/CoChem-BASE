import os

from cochem_base.path_sanitization import get_agents_dir, leak_patterns

agent_dir = str(get_agents_dir())

all_files = []
for root, _dirs, files in os.walk(agent_dir):
    for file in files:
        all_files.append(os.path.join(root, file))

local_leak_patterns = leak_patterns()

for filepath in all_files:
    rel_path = os.path.relpath(filepath, agent_dir)
    # Ignore our own reviewer working dir check script
    if "teamwork_preview_reviewer_2" in rel_path and "check_agents.py" in rel_path:
        continue
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    file_leaks = []
    for idx, line in enumerate(lines, 1):
        for pattern, label in local_leak_patterns:
            if pattern.search(line):
                file_leaks.append((idx, label, line.strip()))
                break
    if file_leaks:
        print(f"File: {rel_path} ({len(file_leaks)} leaks found)")
        for idx, label, line_str in file_leaks:
            print(f"  Line {idx} [{label}]: {line_str}")

