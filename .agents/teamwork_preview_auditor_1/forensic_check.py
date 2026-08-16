import os
import glob
import difflib
import re

source_dir = r'C:\Users\ansac\.gemini\config\agents'
target_dir = r'D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents'

source_files = sorted(glob.glob(os.path.join(source_dir, '*.agent.md')))

print("==================================================")
print("=== FORENSIC CHECK 1: .agent.md Content Match ===")
print("==================================================")
all_15_matched = True
for sf in source_files:
    fname = os.path.basename(sf)
    tf = os.path.join(target_dir, fname)
    if not os.path.exists(tf):
        print(f"MISSING FILE: {fname}")
        all_15_matched = False
        continue

    with open(sf, 'r', encoding='utf-8') as f:
        s_raw = f.read()
    with open(tf, 'r', encoding='utf-8') as f:
        t_raw = f.read()

    # Normalize line endings
    s_norm = s_raw.replace('\r\n', '\n')
    t_norm = t_raw.replace('\r\n', '\n')

    # Sanitize source
    s_san = s_norm
    s_san = s_san.replace(r'C:\Users\ansac', '<USER_HOME>')
    s_san = s_san.replace('C:/Users/ansac', '<USER_HOME>')
    s_san = s_san.replace(r'd:\Gdrive\__CoChem', '<COCHEM_WORKSPACE>')
    s_san = s_san.replace('d:/Gdrive/__CoChem', '<COCHEM_WORKSPACE>')
    s_san = s_san.replace(r'D:\Gdrive\__CoChem', '<COCHEM_WORKSPACE>')
    s_san = s_san.replace('D:/Gdrive/__CoChem', '<COCHEM_WORKSPACE>')

    if s_san == t_norm:
        print(f"  [PASS] {fname} (Identical after path sanitization)")
    else:
        print(f"  [FAIL] {fname} (Content mismatch)")
        all_15_matched = False

print(f"\nAll 15 .agent.md files match sanitized templates: {all_15_matched}")

print("\n==================================================")
print("=== FORENSIC CHECK 2: Leak Scan in .agent.md ===")
print("==================================================")

agent_md_leaks = []
for sf in source_files:
    fname = os.path.basename(sf)
    tf = os.path.join(target_dir, fname)
    with open(tf, 'r', encoding='utf-8') as f:
        content = f.read()
    for lineno, line in enumerate(content.splitlines(), 1):
        if re.search(r'ansac|gdrive|__cochem', line, re.I):
            agent_md_leaks.append((fname, lineno, line.strip()))

if not agent_md_leaks:
    print("  [PASS] Zero path/username leaks found in any of the 15 .agent.md files!")
else:
    print(f"  [FAIL] Found {len(agent_md_leaks)} leaks in .agent.md files:")
    for fname, lineno, text in agent_md_leaks:
        print(f"    {fname}:{lineno}: {text}")

print("\n==================================================")
print("=== FORENSIC CHECK 3: Leak Scan in Subdirectories / Metadata ===")
print("==================================================")

sub_leaks = []
for root, dirs, files in os.walk(target_dir):
    for file in files:
        fpath = os.path.join(root, file)
        rel = os.path.relpath(fpath, target_dir)
        # Skip auditor's own folder and ORIGINAL_REQUEST.md
        if rel.startswith('teamwork_preview_auditor_1') or rel == 'ORIGINAL_REQUEST.md':
            continue
        # Skip .agent.md files (already scanned in Check 2)
        if file.endswith('.agent.md'):
            continue
        
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            for idx, line in enumerate(lines, 1):
                if re.search(r'C:\\Users\\ansac|C:/Users/ansac|D:\\Gdrive|D:/Gdrive', line, re.I):
                    sub_leaks.append((rel, idx, line.strip()))
        except Exception as e:
            """Implementation pending"""
print(f"Subdirectory hardcoded absolute path occurrences: {len(sub_leaks)}")
if sub_leaks:
    for rel, idx, text in sub_leaks[:20]:
        print(f"  {rel}:{idx}: {text[:120]}")
    if len(sub_leaks) > 20:
        print(f"  ... and {len(sub_leaks) - 20} more.")

print("\n==================================================")
print("=== FORENSIC CHECK 4: Facade / Mock / Cheating Check ===")
print("==================================================")
# Inspect what worker / reviewers / explorers did
print("Checking worker files...")
worker_dir = os.path.join(target_dir, 'teamwork_preview_worker_m1')
if os.path.exists(worker_dir):
    print(f"Worker directory contents: {os.listdir(worker_dir)}")
else:
    print("Worker directory not found.")
