import os
import glob

TARGET_DIR = r"D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents"
agent_files = glob.glob(os.path.join(TARGET_DIR, "*.agent.md"))

patterns = [
    "C:\\Users\\ansac",
    "c:\\users\\ansac",
    "D:\\Gdrive\\__CoChem",
    "d:\\gdrive\\__cochem",
    "D:\\Gdrive",
    "d:\\gdrive"
]

all_clean = True
for filepath in agent_files:
    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    found = []
    for p in patterns:
        if p in content or p.lower() in content.lower():
            found.append(p)
            
    if found:
        print(f"[LEAK DETECTED] {filename}: found {found}")
        all_clean = False
    else:
        print(f"[CLEAN] {filename}")

if all_clean:
    print("\nSANIZATION RESULT: PASS — Zero personal/absolute paths found in any of the 15 .agent.md files!")
else:
    print("\nSANIZATION RESULT: FAIL — Personal/absolute paths still exist!")
