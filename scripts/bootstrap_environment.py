"""Create or repair the Python environment used by the CoChem notebook UI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_FILE = REPO_ROOT / "requirements-ui.txt"
REQUIRED_MODULES = (
    "PySide6",
    "ase",
    "cryptography",
    "filelock",
    "h5py",
    "ipykernel",
    "ipywidgets",
    "jinja2",
    "mendeleev",
    "mmh3",
    "networkx",
    "numpy",
    "psutil",
    "pydantic",
    "py3Dmol",
    "pyqtgraph",
    "pyvista",
    "pyvistaqt",
    "nacl",
    "pluggy",
    "rdkit",
    "requests",
    "scipy",
    "voila",
    "vtk",
)


def _python_in(venv_dir: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    return venv_dir / scripts_dir / executable


def _environment_ready(python: Path) -> bool:
    check = (
        "import importlib.metadata, importlib.util, sys; "
        f"modules = {REQUIRED_MODULES!r}; "
        "missing = any(importlib.util.find_spec(name) is None for name in modules); "
        "installed = True; "
        "\ntry: importlib.metadata.version('CoChem-BASE')\n"
        "except importlib.metadata.PackageNotFoundError: installed = False\n"
        "sys.exit(1 if missing or not installed else 0)"
    )
    imports_ok = subprocess.run([str(python), "-c", check], check=False).returncode == 0
    dependencies_ok = (
        subprocess.run(
            [str(python), "-m", "pip", "check"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )
    return imports_ok and dependencies_ok


def ensure_dependencies(python: Path) -> None:
    """Install the UI dependency set when the selected interpreter is incomplete."""
    if _environment_ready(python):
        return
    print(f"Provisioning CoChem UI dependencies in {python.parent.parent}...")
    subprocess.check_call(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(REQUIREMENTS_FILE),
        ],
        cwd=REPO_ROOT,
    )
    if not _environment_ready(python):
        raise RuntimeError(f"Environment validation failed for {python}")


def ensure_current_environment() -> Path:
    """Repair the interpreter currently running a notebook or Python process."""
    python = Path(sys.executable).absolute()
    ensure_dependencies(python)
    return python


def ensure_virtual_environment(venv_dir: Path) -> Path:
    """Create a virtual environment when needed and ensure its UI dependencies."""
    python = _python_in(venv_dir)
    if not python.exists():
        print(f"Creating CoChem Python environment at {venv_dir}...")
        venv.EnvBuilder(with_pip=True).create(venv_dir)
    ensure_dependencies(python)
    return python


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", action="store_true", help="repair the current interpreter")
    parser.add_argument("--launch", action="store_true", help="launch the Voilà application")
    parser.add_argument("--no-browser", action="store_true", help="do not open a local browser")
    parser.add_argument("--venv", type=Path, default=REPO_ROOT / ".venv")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    python = ensure_current_environment() if args.current else ensure_virtual_environment(args.venv)
    if not args.launch:
        return 0

    command = [str(python), "-m", "voila", str(REPO_ROOT / "Start_Here.ipynb")]
    if args.no_browser:
        command.extend(("--no-browser", "--port=8866"))
    return subprocess.call(command, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())