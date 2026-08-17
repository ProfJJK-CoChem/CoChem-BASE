import re

file_path = r'D:\__CoChem\GitHub-Repo\CoChem-BASE\pyproject.toml'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Update Python version requirement
content = re.sub(r'requires-python\s*=\s*">=3\.9"', 'requires-python = ">=3.10"', content)

# Add exhaustive mypy rules
old_mypy = """[tool.mypy]
python_version = "3.14"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
explicit_package_bases = true
exclude = ["build/", "dist/", "rdkit-stubs", "site-packages"]
mypy_path = "stubs"
"""

new_mypy = """[tool.mypy]
python_version = "3.14"
warn_return_any = true
warn_unused_configs = true
explicit_package_bases = true
check_untyped_defs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
disallow_untyped_calls = true
no_implicit_optional = true
exclude = ["build/", "dist/", "rdkit-stubs", "site-packages"]
mypy_path = "stubs"

[[tool.mypy.overrides]]
module = [
    "PySide6.*",
    "pluggy.*",
    "pyqtgraph.*",
    "pyvista.*",
    "pyvistaqt.*",
    "vtk.*",
    "h5py.*",
    "rich.*",
    "scipy.*",
    "rdkit.*"
]
ignore_missing_imports = true
"""

content = content.replace(old_mypy.strip(), new_mypy.strip())

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
