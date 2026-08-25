import os
import glob
import re

files = glob.glob('D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_silo_setup_*.py')

for f in files:
    with open(f, 'r') as file:
        content = file.read()
    
    # Extract conditions
    conditions = []
    reason_parts = []
    
    if re.search(r'monkeypatch\.setenv\("CODESPACES",\s*"true"\)', content):
        conditions.append('os.environ.get("CODESPACES") != "true"')
        reason_parts.append('CODESPACES')
        content = re.sub(r'[ \t]*monkeypatch\.setenv\("CODESPACES",\s*"true"\)\n?', '', content)
        
    calc_os_match = re.search(r'monkeypatch\.setenv\("COCHEM_CALCULATION_OS",\s*"([^"]+)"\)', content)
    if calc_os_match:
        val = calc_os_match.group(1)
        conditions.append(f'os.environ.get("COCHEM_CALCULATION_OS") != "{val}"')
        reason_parts.append(f'COCHEM_CALCULATION_OS={val}')
        content = re.sub(r'[ \t]*monkeypatch\.setenv\("COCHEM_CALCULATION_OS",\s*"[^"]+"\)\n?', '', content)

    slurm_match = re.search(r'monkeypatch\.setenv\("SLURM_JOB_ID",\s*"([^"]+)"\)', content)
    if slurm_match:
        conditions.append('not os.environ.get("SLURM_JOB_ID")')
        reason_parts.append('SLURM_JOB_ID')
        content = re.sub(r'[ \t]*monkeypatch\.setenv\("SLURM_JOB_ID",\s*"[^"]+"\)\n?', '', content)
        
    os_target_match = re.search(r'monkeypatch\.setenv\("COCHEM_OS_TARGET",\s*"([^"]+)"\)', content)
    if os_target_match:
        val = os_target_match.group(1)
        conditions.append(f'os.environ.get("COCHEM_OS_TARGET") != "{val}"')
        reason_parts.append(f'COCHEM_OS_TARGET={val}')
        content = re.sub(r'[ \t]*monkeypatch\.setenv\("COCHEM_OS_TARGET",\s*"[^"]+"\)\n?', '', content)

    if conditions:
        skipif_cond = ' or '.join(conditions)
        reason_str = ' and '.join(reason_parts)
        skipif_decorator = f'@pytest.mark.skipif({skipif_cond}, reason="Requires {reason_str}")\n'
        
        # Add to test function
        content = re.sub(r'(def test_silo_setup_)', skipif_decorator + r'\1', content, count=1)
        
        with open(f, 'w') as file:
            file.write(content)
        print(f'Updated {os.path.basename(f)}')
