with open(r'D:\__CoChem\GitHub-Repo\CoChem-BASE\setup\cochem_setup_orchestrator.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = """    default_interact, default_calc = detect_default_environments()
    if str(interact_env).lower() == "auto":
        interact_env = default_interact
    if str(calc_env).lower() == "auto":
        calc_env = default_calc"""

new_logic = """    if '[MISSING DATA]' in (str(interact_env), str(calc_env)) or str(interact_env).lower() == 'auto' or str(calc_env).lower() == 'auto':
        raise ValueError("CRITICAL: Deployment manifest contains stubbed 'Auto' or '[MISSING DATA]' logic. Computed defaults designed to keep the process alive are strictly forbidden by the Root Cause Resolution Mandate.")"""

content = content.replace(old_logic, new_logic)

with open(r'D:\__CoChem\GitHub-Repo\CoChem-BASE\setup\cochem_setup_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(content)
