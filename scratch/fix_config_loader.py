with open(r'D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\config_loader.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
'''    if not target_path.exists():
        logger.warning(f"Configuration file not found at {target_path}. Instantiating default CoChemConfig.")
        return get_default_cochem_config()''',
'''    if not target_path.exists():
        raise FileNotFoundError(f"CRITICAL: Configuration file not found at {target_path}. Computed defaults designed to keep the process alive are forbidden.")'''
)

content = content.replace(
'''    except (json.JSONDecodeError, ValueError, OSError) as e:
        logger.warning(f"Failed to read or parse JSON config at {target_path}: {e}. Instantiating default CoChemConfig.")
        return get_default_cochem_config()''',
'''    except (json.JSONDecodeError, ValueError, OSError) as e:
        raise ValueError(f"CRITICAL: Failed to read or parse JSON config at {target_path}: {e}. Computed defaults designed to keep the process alive are forbidden.") from e'''
)

content = content.replace(
'''    hardware = raw_data.get("hardware")
    if isinstance(hardware, dict) and str(hardware.get("os_target", "")).lower() in {"", "auto"}:
        hardware["os_target"] = f"{platform.system().lower()}_{platform.machine().lower()}"''',
'''    # Computed defaults for os_target removed per Exception Deflection Test mandate.'''
)

content = content.replace(
'''    except Exception as e:
        logger.warning(f"Config schema validation error for {target_path}: {e}. Instantiating default CoChemConfig.")
        return get_default_cochem_config()''',
'''    except Exception as e:
        raise ValueError(f"CRITICAL: Config schema validation error for {target_path}: {e}. Computed defaults designed to keep the process alive are forbidden.") from e'''
)

with open(r'D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\config_loader.py', 'w', encoding='utf-8') as f:
    f.write(content)
