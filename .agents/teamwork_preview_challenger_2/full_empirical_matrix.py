import os
import difflib

SOURCE_DIR = r"C:\Users\ansac\.gemini\config\agents"
TARGET_DIR = r"D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents"

agent_files = [
    "0rchestrator.agent.md",
    "artist.agent.md",
    "cochem-audit.agent.md",
    "cochem-coder.agent.md",
    "cochem-debug.agent.md",
    "cochem-helper.agent.md",
    "cochem-improve.agent.md",
    "cochem-scribe.agent.md",
    "cochem-sdp_manager.agent.md",
    "cochem-tester.agent.md",
    "educator.agent.md",
    "researcher.agent.md",
    "teacher.agent.md",
    "ui.agent.md",
    "web_mcp.agent.md"
]

print("=== TEST 1: Source (config/agents) with <USER_HOME>, <COCHEM_WORKSPACE>, <GDRIVE_ROOT> replaced by actual paths vs Target (CoChem-BASE/.agents) ===")
# In Test 1, we took Source and replaced <VAR> with path. Since Source had actual paths (D:\Gdrive\__CoChem) and Target had <COCHEM_WORKSPACE>, Source replaced became actual paths, while Target had placeholders. Result was MISMATCH for all 15.

print("\n=== TEST 2: Target (CoChem-BASE/.agents) with <USER_HOME>, <COCHEM_WORKSPACE>, <GDRIVE_ROOT> replaced by actual paths vs Source (config/agents) ===")
test2_matches = 0
for filename in agent_files:
    src_path = os.path.join(SOURCE_DIR, filename)
    tgt_path = os.path.join(TARGET_DIR, filename)
    
    with open(src_path, "r", encoding="utf-8") as f:
        src_content = f.read()
        
    with open(tgt_path, "r", encoding="utf-8") as f:
        tgt_content = f.read()
        
    tgt_expanded = tgt_content.replace("<COCHEM_WORKSPACE>", r"D:\Gdrive\__CoChem") \
                              .replace("<GDRIVE_ROOT>", r"D:\Gdrive") \
                              .replace("<USER_HOME>", r"C:\Users\ansac")
                              
    if tgt_expanded == src_content:
        print(f"[MATCH] {filename}")
        test2_matches += 1
    else:
        print(f"[MISMATCH] {filename}")
        diff = list(difflib.unified_diff(
            src_content.splitlines(keepends=True),
            tgt_expanded.splitlines(keepends=True),
            fromfile=f"src/{filename}",
            tofile=f"tgt_expanded/{filename}"
        ))
        for line in diff:
            print(line.rstrip('\r\n'))

print(f"Test 2 Total Matches: {test2_matches} / 15")

print("\n=== TEST 3: Source (config/agents) sanitized (actual paths replaced by <COCHEM_WORKSPACE>, <GDRIVE_ROOT>) vs Target (CoChem-BASE/.agents) ===")
test3_matches = 0
for filename in agent_files:
    src_path = os.path.join(SOURCE_DIR, filename)
    tgt_path = os.path.join(TARGET_DIR, filename)
    
    with open(src_path, "r", encoding="utf-8") as f:
        src_content = f.read()
        
    with open(tgt_path, "r", encoding="utf-8") as f:
        tgt_content = f.read()
        
    # Order matters: replace longer path D:\Gdrive\__CoChem first, then D:\Gdrive
    src_sanitized = src_content.replace(r"D:\Gdrive\__CoChem", "<COCHEM_WORKSPACE>") \
                               .replace(r"D:\Gdrive", "<GDRIVE_ROOT>") \
                               .replace(r"C:\Users\ansac", "<USER_HOME>")
                               
    if src_sanitized == tgt_content:
        print(f"[MATCH] {filename}")
        test3_matches += 1
    else:
        print(f"[MISMATCH] {filename}")
        diff = list(difflib.unified_diff(
            src_sanitized.splitlines(keepends=True),
            tgt_content.splitlines(keepends=True),
            fromfile=f"src_sanitized/{filename}",
            tofile=f"tgt/{filename}"
        ))
        for line in diff:
            print(line.rstrip('\r\n'))

print(f"Test 3 Total Matches: {test3_matches} / 15")
