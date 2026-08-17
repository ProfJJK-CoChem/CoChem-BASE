import re

file_path = r'D:\__CoChem\GitHub-Repo\CoChem-BASE\headless_run.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add platform import
if 'import platform' not in content:
    content = content.replace('import sys', 'import sys\nimport platform')

# Fix Exception Deflection 1
old_provision = """except Exception as e:
    logger.info(f"Error during setup: {e}")"""
new_provision = """except Exception as e:
    logger.info(f"Error during setup: {e}")
    raise ValueError(f"CRITICAL: Provisioning failed. Exception Deflection blocked.") from e"""
content = content.replace(old_provision, new_provision)

# Fix Exception Deflection 2
old_tests = """except Exception as e:
    logger.info(f"❌ Error running tests: {e}")"""
new_tests = """except Exception as e:
    logger.info(f"❌ Error running tests: {e}")
    raise ValueError(f"CRITICAL: Test suite crashed. Exception Deflection blocked.") from e"""
content = content.replace(old_tests, new_tests)

# Fix mocked data
old_mock = """interface_env = 'Local-Windows (WSL)'
calc_env = 'GitHub Actions'
os.environ['COCHEM_INTERFACE_ENV'] = interface_env
os.environ['COCHEM_CALC_ENV'] = calc_env"""
new_mock = """interface_env = {
    'Windows': 'Local-Windows (WSL)',
    'Darwin': 'Local-MacOS (OrbStack)',
    'Linux': 'Local-Linux (Deb)',
}.get(platform.system(), 'Codespaces')
if os.environ.get('CODESPACES'):
    interface_env = 'Codespaces'
calc_env = interface_env if interface_env != 'Codespaces' else 'GitHub Actions'

os.environ['COCHEM_INTERFACE_ENV'] = interface_env
os.environ['COCHEM_CALC_ENV'] = calc_env"""
content = content.replace(old_mock, new_mock)

# Fix logging header
content = re.sub(r'logger\.info\("\\n==== TASK 2:.*?====\"\)', 'logger.info("\\n==== TASK 2: Running Environment Preflight Checks ====")', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
