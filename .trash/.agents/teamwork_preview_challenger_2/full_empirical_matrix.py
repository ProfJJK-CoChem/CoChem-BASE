import difflib
import os

from cochem_base.path_sanitization import (
    get_agent_templates_dir,
    get_agents_dir,
    placeholder_values,
    sanitize_local_paths,
)

SOURCE_DIR = str(get_agent_templates_dir())
TARGET_DIR = str(get_agents_dir())
PLACEHOLDER_VALUES = {key: str(value) for key, value in placeholder_values().items()}

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

print("=== TEST 1: Source templates compared with dynamically mapped target paths ===")

print("\n=== TEST 2: Target (CoChem-BASE/.agents) with <USER_HOME>, <COCHEM_WORKSPACE>, <GDRIVE_ROOT> replaced by actual paths vs Source (config/agents) ===")
test2_matches = 0
for filename in agent_files:
    src_path = os.path.join(SOURCE_DIR, filename)
    tgt_path = os.path.join(TARGET_DIR, filename)

    with open(src_path, "r", encoding="utf-8") as f:
        src_content = f.read()

    with open(tgt_path, "r", encoding="utf-8") as f:
        tgt_content = f.read()

    tgt_expanded = tgt_content
    for placeholder, value in PLACEHOLDER_VALUES.items():
        tgt_expanded = tgt_expanded.replace(placeholder, value)

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

    src_sanitized = sanitize_local_paths(src_content)

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
