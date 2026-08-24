import sys
from pathlib import Path

base_root = Path(__file__).resolve().parent
repo_root = base_root.parent

for path in [repo_root / "CoChem-BENCH", repo_root / "CoChem-BASE", base_root / "src", base_root]:
    if path.exists():
        p_str = str(path)
        if p_str in sys.path:
            sys.path.remove(p_str)
        sys.path.insert(0, p_str)
