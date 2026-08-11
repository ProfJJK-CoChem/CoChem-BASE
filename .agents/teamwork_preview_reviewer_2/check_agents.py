import os
import glob
import re

agent_dir = r"D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents"
config_dir = r"C:\Users\ansac\.gemini\config\agents"

# 1. Check all files under .agents recursively for personal path leaks
print("=== RECURSIVE PATH LEAK CHECK ACROSS ALL FILES IN .AGENTS ===")
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

total_leaks_in_agents_dir = []

for filepath in all_files:
    rel_path = os.path.relpath(filepath, agent_dir)
    # Skip checking reviewer's own script/output files or dispatch if needed, but let's check everything and report context
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    file_leaks = []
    for idx, line in enumerate(lines, 1):
        for pattern, label in leak_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                file_leaks.append((idx, label, line.strip()))
                break
    if file_leaks:
        total_leaks_in_agents_dir.append((rel_path, file_leaks))

print(f"Total files checked: {len(all_files)}")
print(f"Files with potential path leaks: {len(total_leaks_in_agents_dir)}")
for rel_path, leaks in total_leaks_in_agents_dir:
    print(f"\nFile: {rel_path} ({len(leaks)} matches)")
    for line_no, label, line_str in leaks[:10]: # print first 10 matches
        print(f"  Line {line_no} [{label}]: {line_str[:120]}")

# 2. Detailed Frontmatter and Capability Inspection for 15 .agent.md files
print("\n=== DETAILED 15 .AGENT.MD INSPECTION ===")
agent_files = sorted(glob.glob(os.path.join(agent_dir, "*.agent.md")))

for filepath in agent_files:
    fname = os.path.basename(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    print(f"\n--- {fname} ---")
    fm_match = re.search(r'^---\r?\n(.*?)\r?\n---', content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        print("YAML Frontmatter:")
        print(fm_text.strip())
    else:
        print("CRITICAL: No YAML frontmatter!")
        
    # Check required fields
    has_write_tools = "enable_write_tools: true" in content
    has_mcp_tools = "enable_mcp_tools: true" in content
    print(f"  enable_write_tools: {has_write_tools}")
    print(f"  enable_mcp_tools: {has_mcp_tools}")
    
    # Check body completeness
    body = content[fm_match.end():] if fm_match else content
    print(f"  Body length: {len(body)} chars, {len(body.splitlines())} lines")

# 3. Compare with config_dir templates if present
print("\n=== COMPARISON WITH CONFIG TEMPLATES ===")
if os.path.exists(config_dir):
    config_files = sorted(glob.glob(os.path.join(config_dir, "*.agent.md")))
    print(f"Found {len(config_files)} files in config directory {config_dir}")
    for cf in config_files:
        cf_name = os.path.basename(cf)
        target_path = os.path.join(agent_dir, cf_name)
        if os.path.exists(target_path):
            with open(cf, 'r', encoding='utf-8') as f1, open(target_path, 'r', encoding='utf-8') as f2:
                c1 = f1.read()
                c2 = f2.read()
            # Perform sanitization simulation on c1 to see if c2 equals sanitized c1
            sanitized_c1 = c1.replace(r"C:\Users\ansac", "<USER_HOME>") \
                            .replace(r"C:/Users/ansac", "<USER_HOME>") \
                            .replace(r"D:\Gdrive\__CoChem", "<COCHEM_WORKSPACE>") \
                            .replace(r"D:/Gdrive/__CoChem", "<COCHEM_WORKSPACE>") \
                            .replace(r"D:\Gdrive", "<GDRIVE_ROOT>") \
                            .replace(r"D:/Gdrive", "<GDRIVE_ROOT>")
            matches_sanitized = (sanitized_c1 == c2)
            print(f"File {cf_name}: matches sanitized config = {matches_sanitized}")
            if not matches_sanitized:
                print(f"  Config len: {len(c1)}, Target len: {len(c2)}")
                print(f"  Sanitized Config len: {len(sanitized_c1)}")
else:
    print(f"Config directory {config_dir} does not exist or is inaccessible.")

