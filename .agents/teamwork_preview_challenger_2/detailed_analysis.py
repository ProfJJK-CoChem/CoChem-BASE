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

print("=== RAW VERBATIM COMPARISON (No Replacements) ===")
raw_matches = 0
for filename in agent_files:
    src_path = os.path.join(SOURCE_DIR, filename)
    tgt_path = os.path.join(TARGET_DIR, filename)
    with open(src_path, "r", encoding="utf-8") as f:
        src_raw = f.read()
    with open(tgt_path, "r", encoding="utf-8") as f:
        tgt_raw = f.read()
    if src_raw == tgt_raw:
        print(f"RAW MATCH: {filename}")
        raw_matches += 1
    else:
        print(f"RAW MISMATCH: {filename}")

print(f"Total raw matches: {raw_matches} / 15")
