import os
import subprocess
import sys
from pathlib import Path

BASE_ROOT = Path(__file__).resolve().parents[1]
SILO_SETUP_SCRIPT = BASE_ROOT / "setup" / "cochem_base_silo_setup.py"


def test_silo_script_ignores_stale_pythonpath_package(tmp_path: Path) -> None:
    stale_package = tmp_path / "cochem_base"
    stale_package.mkdir()
    (stale_package / "__init__.py").write_text(
        "raise RuntimeError('stale package imported')\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, "-B", str(SILO_SETUP_SCRIPT), "--probe-import"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30.0,
    )

    imported_package = Path(result.stdout.strip()).resolve()
    assert imported_package.is_relative_to(BASE_ROOT / "cochem_base")
