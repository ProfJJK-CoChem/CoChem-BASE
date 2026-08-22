import sys
from pathlib import Path

base_root = Path(__file__).resolve().parent
repo_root = base_root.parent

for path in [base_root, repo_root / "CoChem-BENCH", repo_root / "CoChem-BASE", base_root / "src"]:
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))
