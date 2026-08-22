import ast
from pathlib import Path
import pytest

root = Path(r"D:\__CoChem\GitHub-Repo\CoChem-BASE")

# 1. Encoding and line ending audit
files = ["README.md", "test_suite/test_readme.py", "tests/test_readme.py"]
for rel in files:
    f = root / rel
    assert f.exists(), f"{rel} does not exist"
    data = f.read_bytes()
    assert len(data) > 0, f"{rel} is empty"
    assert not data.startswith(b"\xef\xbb\xbf"), f"{rel} has UTF-8 BOM"
    assert b"\r\n" not in data, f"{rel} has CRLF line endings"
    assert b"\r" not in data, f"{rel} has CR line endings"
    assert b"\n" in data, f"{rel} missing LF"
    text = data.decode("utf-8")
    print(f"[OK] {rel}: Size={len(data)} bytes, UTF-8 LF, No BOM")

# 2. Zero-Mock AST Verification
for test_rel in ["test_suite/test_readme.py", "tests/test_readme.py"]:
    test_path = root / test_rel
    tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Mock in import {alias.name} in {test_rel}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "mock" not in mod.lower(), f"Mock in from-import {mod} in {test_rel}"
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Mock in imported symbol {alias.name} in {test_rel}"
    print(f"[OK] {test_rel}: Zero-Mock AST import check PASSED")

# 3. Anti-Placeholder Invariant
prohibited = ["TODO", "FIXME", "TBD", "PLACEHOLDER", "DUMMY_TOKEN", "MOCK_LOGIC", "FOO_BAR", "LOREM IPSUM"]
for rel in files:
    content = (root / rel).read_text(encoding="utf-8")
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        if "test_readme.py" in rel:
            # Skip definition lines of the test that asserts tokens
            if "prohibited_tokens" in line or any(f'"{p}"' in line or f"'{p}'" in line for p in prohibited):
                continue
        for p in prohibited:
            assert p not in line, f"Found {p} at {rel}:{idx}: {line}"
    print(f"[OK] {rel}: Anti-Placeholder scan PASSED")

print("All static checks PASSED successfully!")
