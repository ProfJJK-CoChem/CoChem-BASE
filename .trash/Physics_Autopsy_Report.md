# Physics Autopsy Report: Timeout in `verify_core_integrity.py`

## Incident Summary
The verification script `verify_core_integrity.py` encountered a `[HARD_ABORT: PHYSICS WALL]` due to timing out after exceeding its 60.0s maximum execution limit in `audit.py`.

## Root Cause Analysis
- `audit.py` triggers `verify_core_integrity.py` with the repository root (`D:\__CoChem\GitHub-Repo`).
- `verify_core_integrity.py` then passes this root directory to `anti_spoof_linter.py`.
- `anti_spoof_linter.py` originally used `target.rglob("*.py")` to locate all Python scripts and `ast.parse` each file to search for banned parallel libraries.
- The repository root contains large environment/cache directories (`.venv`, `.conda`, `__pycache__`, `.pytest_cache`) holding thousands of third-party Python files.
- Parsing all these unnecessary files took longer than 60 seconds, resulting in a timeout.

## Resolution
The file traversal logic in `anti_spoof_linter.py` was rewritten to use `os.walk` instead of `rglob`. This allows modifying the `dirs` list in place to prune `.venv`, `.conda`, `__pycache__`, and `.pytest_cache` entirely, preventing the linter from searching them. By skipping these directories, the script execution time falls well within the 60.0s threshold.
