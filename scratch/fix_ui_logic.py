
file_path = r'D:\__CoChem\GitHub-Repo\CoChem-BASE\run_ui_logic.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Inject dynamic target resolution instead of hardcoded stubs
old_mock = """        # Apply dropdown selections setting environment/config conceptually
        # Though the logic primarily runs run_all_preflight_checks
        os.environ['COCHEM_INTERFACE_ENV'] = 'Codespaces'
        os.environ['COCHEM_CALC_ENV'] = 'GitHub Actions'"""

new_mock = """        # Apply dropdown selections setting environment/config conceptually
        # Though the logic primarily runs run_all_preflight_checks
        import platform
        interface_env = {
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

# Fix 2: Eradicate Exception Deflection
old_except = """    except Exception as e:
        logger.error(f"ERROR: {e}")
        traceback.print_exc()
        return {"status": "FAILURE", "error": str(e)}"""

new_except = """    except Exception as e:
        logger.error(f"ERROR: {e}")
        traceback.print_exc()
        raise ValueError("CRITICAL: UI Logic run failed. Exception Deflection blocked. Process crashing.") from e"""

content = content.replace(old_except, new_except)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
