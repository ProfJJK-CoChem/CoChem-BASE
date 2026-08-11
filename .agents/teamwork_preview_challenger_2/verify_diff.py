import os
import difflib
import sys

SOURCE_DIR = r"C:\Users\ansac\.gemini\config\agents"
TARGET_DIR = r"D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents"

REPLACEMENTS = [
    ("<USER_HOME>", r"C:\Users\ansac"),
    ("<COCHEM_WORKSPACE>", r"D:\Gdrive\__CoChem"),
    ("<GDRIVE_ROOT>", r"D:\Gdrive")
]

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

all_identical = True
report_lines = []

report_lines.append("=== EMPIRICAL DIFF VERIFICATION REPORT ===")
report_lines.append(f"Source Directory: {SOURCE_DIR}")
report_lines.append(f"Target Directory: {TARGET_DIR}")
report_lines.append("Replacements applied to source files:")
for old, new in REPLACEMENTS:
    report_lines.append(f"  '{old}' -> '{new}'")
report_lines.append("-" * 60)

for filename in agent_files:
    src_path = os.path.join(SOURCE_DIR, filename)
    tgt_path = os.path.join(TARGET_DIR, filename)
    
    if not os.path.exists(src_path):
        report_lines.append(f"ERROR: Source file missing: {src_path}")
        all_identical = False
        continue
    if not os.path.exists(tgt_path):
        report_lines.append(f"ERROR: Target file missing: {tgt_path}")
        all_identical = False
        continue
        
    with open(src_path, "r", encoding="utf-8") as f:
        src_raw = f.read()
        
    # Apply replacements
    expected_content = src_raw
    for old, new in REPLACEMENTS:
        expected_content = expected_content.replace(old, new)
        
    with open(tgt_path, "r", encoding="utf-8") as f:
        actual_content = f.read()
        
    if expected_content == actual_content:
        report_lines.append(f"[PASS] {filename}: EXACT MATCH ({len(actual_content)} chars, {len(actual_content.splitlines())} lines)")
    else:
        all_identical = False
        report_lines.append(f"[FAIL] {filename}: MISMATCH DETECTED!")
        
        expected_lines = expected_content.splitlines(keepends=True)
        actual_lines = actual_content.splitlines(keepends=True)
        
        diff = list(difflib.unified_diff(
            expected_lines, actual_lines,
            fromfile=f"expected/{filename}",
            tofile=f"actual/{filename}"
        ))
        report_lines.append("Diff output:")
        for line in diff:
            report_lines.append(line.rstrip('\r\n'))
        report_lines.append("-" * 60)

report_lines.append("=" * 60)
if all_identical:
    report_lines.append("VERDICT: APPROVE - All 15 files are 100% identical after variable replacement.")
else:
    report_lines.append("VERDICT: REJECT - Discrepancies found between source templates and target agent files.")

report_text = "\n".join(report_lines)
print(report_text)

with open(r"D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents\teamwork_preview_challenger_2\verification_results.txt", "w", encoding="utf-8") as f:
    f.write(report_text)
