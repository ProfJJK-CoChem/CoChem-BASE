
file_path = r'D:\__CoChem\GitHub-Repo\CoChem-BASE\rewrite_notebook.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix cell 1 setup exception
old_setup = """        \"                except Exception as e:\\n\",
        \"                    print(f\\\"Error during setup: {e}\\\")\\n\","""
new_setup = """        \"                except Exception as e:\\n\",
        \"                    print(f\\\"Error during setup: {e}\\\")\\n\",
        \"                    raise ValueError(f\\\"CRITICAL: Provisioning failed. Exception Deflection blocked.\\\") from e\\n\","""
content = content.replace(old_setup, new_setup)

# Fix cell 2 keep exception
old_keep_test = """        \"        except Exception as e:\\n\",
        \"            print(f\\\"❌ Error running tests: {e}\\\")\\n\","""
new_keep_test = """        \"        except Exception as e:\\n\",
        \"            print(f\\\"❌ Error running tests: {e}\\\")\\n\",
        \"            raise ValueError(f\\\"CRITICAL: Test suite crashed. Exception Deflection blocked.\\\") from e\\n\","""
content = content.replace(old_keep_test, new_keep_test)

# Fix cell 2 new exception
old_set_test = """        \"                except Exception as e:\\n\",
        \"                    print(f\\\"❌ Error running tests: {e}\\\")\\n\",
        \"                \\n\","""
new_set_test = """        \"                except Exception as e:\\n\",
        \"                    print(f\\\"❌ Error running tests: {e}\\\")\\n\",
        \"                    raise ValueError(f\\\"CRITICAL: Test suite crashed. Exception Deflection blocked.\\\") from e\\n\",
        \"                \\n\","""
content = content.replace(old_set_test, new_set_test)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
