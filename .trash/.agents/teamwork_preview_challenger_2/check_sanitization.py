import glob
import os

from cochem_base.path_sanitization import get_agents_dir, leak_patterns

TARGET_DIR = str(get_agents_dir())
agent_files = glob.glob(os.path.join(TARGET_DIR, "*.agent.md"))

patterns = leak_patterns()

all_clean = True
for filepath in agent_files:
    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    found = []
    for pattern, label in patterns:
        if pattern.search(content):
            found.append(label)

    if found:
        print(f"[LEAK DETECTED] {filename}: found {found}")
        all_clean = False
    else:
        print(f"[CLEAN] {filename}")

if all_clean:
    print("\nSANIZATION RESULT: PASS — Zero personal/absolute paths found in any of the 15 .agent.md files!")
else:
    print("\nSANIZATION RESULT: FAIL — Personal/absolute paths still exist!")
