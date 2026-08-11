import os
import re

agent_dir = r"D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents"

all_files = []
for root, dirs, files in os.walk(agent_dir):
    for file in files:
        all_files.append(os.path.join(root, file))

leak_patterns = [
    (r"C:\\Users\\ansac", "C:\\Users\\ansac"),
    (r"C:/Users/ansac", "C:/Users/ansac"),
    (r"D:\\Gdrive\\__CoChem", "D:\\Gdrive\\__CoChem"),
    (r"D:/Gdrive/__CoChem", "D:/Gdrive/__CoChem"),
    (r"D:\\Gdrive", "D:\\Gdrive"),
    (r"D:/Gdrive", "D:/Gdrive"),
]

for filepath in all_files:
    rel_path = os.path.relpath(filepath, agent_dir)
    # Ignore our own reviewer working dir check script
    if "teamwork_preview_reviewer_2" in rel_path and "check_agents.py" in rel_path:
        continue
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    file_leaks = []
    for idx, line in enumerate(lines, 1):
        for pattern, label in leak_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                file_leaks.append((idx, label, line.strip()))
                break
    if file_leaks:
        print(f"File: {rel_path} ({len(file_leaks)} leaks found)")
        for idx, label, line_str in file_leaks:
            print(f"  Line {idx} [{label}]: {line_str}")

