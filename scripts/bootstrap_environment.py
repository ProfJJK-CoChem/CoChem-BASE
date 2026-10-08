"""Create or repair the Python environment used by the CoChem notebook UI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
import venv
import webbrowser
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
    "jax",
    "jaxlib",
    "matplotlib",
    "mendeleev",
    "mmh3",
    "networkx",
    "numpy",
    "psutil",
    "pydantic",
    "qcelemental",
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


def artifact_directory() -> Path:
    root = Path(os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")).expanduser().resolve()
    if root == REPO_ROOT or REPO_ROOT in root.parents:
        raise ValueError("CoChem runtime data must be outside the source checkout")
    return root


def build_environment() -> dict[str, str]:
    try:
        from scripts.hosted_dashboard import setup_build_environment
    except ModuleNotFoundError:
        from hosted_dashboard import setup_build_environment
    environment = setup_build_environment(os.environ.copy())
    if any(key.startswith("COCHEM_SOURCE_QUARANTINE_") for key in os.environ):
        from ci_tools.source_quarantine import source_child_environment

        environment = source_child_environment(environment, selected_source=REPO_ROOT)
    return environment


def _python_in(venv_dir: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    return venv_dir / scripts_dir / executable


def _environment_ready(python: Path, *, explain: bool = False) -> bool:
    """Check this source's dependency contract, rather than any installed BASE."""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = list(project.get("dependencies", []))
    for group in ("ui", "symmetry"):
        requirements.extend(project.get("optional-dependencies", {}).get(group, []))
    for file in (REPO_ROOT / "requirements.txt", REQUIREMENTS_FILE):
        for raw in file.read_text(encoding="utf-8").splitlines():
            value = raw.split("#", 1)[0].strip()
            if value and value != "-e .":
                if value.startswith("-"):
                    raise ValueError("The bootstrap dependency contract contains an unsupported directive")
                requirements.append(value)
    contract = {"version": project["version"], "python": project["requires-python"],
                "requirements": requirements, "modules": REQUIRED_MODULES, "source": str(REPO_ROOT)}
    check = """import hashlib, importlib.metadata as metadata, importlib.util, json, pathlib, sys
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.markers import default_environment
contract=json.loads(sys.argv[1])
def fail(message):
    print(message,file=sys.stderr)
    sys.exit(1)
if not SpecifierSet(contract['python']).contains('.'.join(map(str,sys.version_info[:3]))):
    fail('Python version does not satisfy this BASE source contract')
if metadata.version('CoChem-BASE') != contract['version']:
    fail('Installed BASE version differs from the selected source version')
prefix=pathlib.Path(sys.prefix).resolve()
source=pathlib.Path(contract['source']).resolve()
for name in contract['modules']:
    spec=importlib.util.find_spec(name)
    if spec is None or spec.origin is None or not pathlib.Path(spec.origin).resolve().is_relative_to(prefix):
        fail('Required dependency is unavailable or outside the interface environment: '+name)
base=importlib.util.find_spec('cochem_base.cli')
expected=source/'src/cochem_base/cli.py'
if base is None or base.origin is None:
    fail('Imported BASE code does not belong to the selected source')
origin=pathlib.Path(base.origin).resolve()
if origin != expected and (not origin.is_relative_to(prefix) or not expected.is_file()
        or hashlib.sha256(origin.read_bytes()).digest() != hashlib.sha256(expected.read_bytes()).digest()):
    fail('Imported BASE code does not belong to the selected source')
if origin != expected:
    for declared in (source/'src/cochem_base').rglob('*.py'):
        installed=origin.parent/declared.relative_to(source/'src/cochem_base')
        if (not installed.is_file() or not installed.resolve().is_relative_to(prefix)
                or hashlib.sha256(installed.read_bytes()).digest()!=hashlib.sha256(declared.read_bytes()).digest()):
            fail('Installed BASE code differs from selected source: '+declared.relative_to(source).as_posix())
pending=[(text,'') for text in contract['requirements']]
seen=set()
while pending:
    text,extra=pending.pop()
    if (text,extra) in seen:
        continue
    seen.add((text,extra))
    requirement=Requirement(text)
    environment=default_environment(); environment['extra']=extra
    if requirement.marker and not requirement.marker.evaluate(environment):
        continue
    distribution=metadata.distribution(requirement.name)
    if requirement.url or not requirement.specifier.contains(distribution.version,prereleases=True):
        fail('Installed dependency does not satisfy '+str(requirement)+'; found '+distribution.version)
    for selected_extra in requirement.extras:
        pending.extend((child,selected_extra) for child in distribution.requires or [])
"""
    probe = subprocess.run([str(python), "-B", "-c", check, json.dumps(contract)], check=False,
                           capture_output=True, text=True, env=build_environment())
    dependencies = subprocess.run(
            [str(python), "-m", "pip", "check"],
            check=False,
            capture_output=True,
            text=True,
            env=build_environment(),
        )
    if explain and (probe.returncode or dependencies.returncode):
        reason = probe.stderr if probe.returncode else dependencies.stdout + dependencies.stderr
        print("Interface environment validation: " + reason.strip()[-2000:], file=sys.stderr)
    return probe.returncode == 0 and dependencies.returncode == 0


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
            "-e",
            ".[ui,symmetry]",
            "-r",
            str(REQUIREMENTS_FILE),
            "-r",
            str(REPO_ROOT / "requirements.txt"),
        ],
        cwd=REPO_ROOT,
        env=build_environment(),
    )
    if not _environment_ready(python, explain=True):
        raise RuntimeError(f"Environment validation failed for {python}")


def ensure_current_environment() -> Path:
    """Repair the interpreter currently running a notebook or Python process."""
    python = Path(sys.executable).absolute()
    ensure_dependencies(python)
    return python


def ensure_virtual_environment(venv_dir: Path) -> Path:
    """Create a virtual environment when needed and ensure its UI dependencies."""
    venv_dir = venv_dir.expanduser().resolve()
    if venv_dir == REPO_ROOT or REPO_ROOT in venv_dir.parents:
        raise ValueError("The interface environment must be outside the source checkout")
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
    parser.add_argument("--venv", type=Path, help="external interface environment; defaults to the artifact directory's ui-env")
    parser.add_argument("--artifacts", type=Path, default=artifact_directory())
    parser.add_argument("--port", type=int, default=8866)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--min-disk-space-gb", type=float, default=1.0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    artifacts = args.artifacts.expanduser().resolve()
    python = ensure_current_environment() if args.current else ensure_virtual_environment(args.venv or artifacts / "ui-env")
    if not args.launch:
        return 0

    try:
        from scripts.hosted_dashboard import main as dashboard_main
        from scripts.hosted_dashboard import setup_dashboard, validate_setup
    except ModuleNotFoundError:
        from hosted_dashboard import main as dashboard_main
        from hosted_dashboard import setup_dashboard, validate_setup
    os.environ.setdefault("COCHEM_STUDENT_AUTO_SETUP", "true")
    os.environ.setdefault("COCHEM_MODULES", "topos torq")
    try:
        validate_setup(python, artifacts)
    except (subprocess.SubprocessError, OSError, ValueError):
        setup_dashboard(python, artifacts, args.min_disk_space_gb)
    # The managed entry point verifies and selects an already approved external
    # runtime. Relaunching a native shortcut must not undo a GUI-applied update.
    result = dashboard_main(["start", "--artifacts", str(artifacts), "--venv", str(python.parent.parent),
                             "--port", str(args.port), "--timeout", str(args.timeout)])
    if result:
        return result
    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{args.port}/")
    print(f"CoChem is ready at http://127.0.0.1:{args.port}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
