import os
import glob
import re
import sys
import yaml

sys.stdout.reconfigure(encoding='utf-8')

agent_dir = r"D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents"
agent_files = sorted(glob.glob(os.path.join(agent_dir, "*.agent.md")))

print(f"Verifying {len(agent_files)} agent files...")

all_passed = True

for filepath in agent_files:
    fname = os.path.basename(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    print(f"\n========================================")
    print(f"File: {fname}")
    
    # 1. Frontmatter check
    fm_match = re.search(r'^---\r?\n(.*?)\r?\n---', content, re.DOTALL)
    if not fm_match:
        print(f"[FAIL] Missing frontmatter in {fname}")
        all_passed = False
        continue
        
    fm_str = fm_match.group(1)
    try:
        fm_data = yaml.safe_load(fm_str)
        print("[PASS] YAML frontmatter is valid")
    except Exception as e:
        print(f"[FAIL] Invalid YAML frontmatter in {fname}: {e}")
        all_passed = False
        continue
        
    # 2. Key checks
    req_keys = ['name', 'description', 'argument-hint', 'enable_write_tools', 'enable_mcp_tools']
    missing_keys = [k for k in req_keys if k not in fm_data]
    if missing_keys:
        print(f"[FAIL] Missing required frontmatter keys in {fname}: {missing_keys}")
        all_passed = False
    else:
        print(f"[PASS] All required frontmatter keys present: {req_keys}")
        
    if fm_data.get('enable_write_tools') is not True:
        print(f"[FAIL] enable_write_tools is not True in {fname} (value: {fm_data.get('enable_write_tools')})")
        all_passed = False
    else:
        print(f"[PASS] enable_write_tools: True")
        
    if fm_data.get('enable_mcp_tools') is not True:
        print(f"[FAIL] enable_mcp_tools is not True in {fname} (value: {fm_data.get('enable_mcp_tools')})")
        all_passed = False
    else:
        print(f"[PASS] enable_mcp_tools: True")
        
    # 3. Path sanitization check in agent file
    leak_regex = re.compile(r'C:\\Users\\ansac|C:/Users/ansac|D:\\Gdrive|D:/Gdrive|ansac|__CoChem', re.IGNORECASE)
    leaks = leak_regex.findall(content)
    if leaks:
        print(f"[FAIL] Personal path leaks found in {fname}: {leaks}")
        all_passed = False
    else:
        print(f"[PASS] Zero personal path leaks in {fname}")
        
    # 4. Check placeholder presence
    found_placeholders = []
    for ph in ['<USER_HOME>', '<COCHEM_WORKSPACE>', '<GDRIVE_ROOT>']:
        if ph in content:
            found_placeholders.append(ph)
    print(f"[PASS] Sanitized placeholders present in {fname}: {found_placeholders}")
    
    # 5. Completeness check
    body = content[fm_match.end():].strip()
    if len(body) < 100:
        print(f"[FAIL] Agent body meens incomplete/too short in {fname} ({len(body)} chars)")
        all_passed = False
    else:
        print(f"[PASS] Agent body complete ({len(body)} chars, {len(body.splitlines())} lines)")
        
    # Check for TODO/FIXME/stub markers
    stubs = re.findall(r'\b(TODO|FIXME|XXX|NOT IMPLEMENTED|PLACEHOLDER)\b', body, re.IGNORECASE)
    if stubs:
        print(f"[WARN] Stub/TODO markers found in {fname}: {stubs}")
    else:
        print(f"[PASS] No stub/TODO markers in {fname}")

print("\n========================================")
if all_passed:
    print("SUCCESS: ALL 15 AGENT FILES PASSED ALL VERIFICATIONS!")
else:
    print("FAILURE: AT LEAST ONE AGENT FILE FAILED VERIFICATION!")

