"""Install and start the Codespaces dashboard with runtime files outside the checkout.

This also provides a locally executable acceptance path for the Codespaces lifecycle.
The forwarded port remains private. Codespaces can prepare Actions jobs without
local calculation engines; the legacy local profile still requires full Stage 0.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def calculation_environment(selection: str | None = None) -> str:
    """Keep local as the explicit legacy default outside the Codespaces profile."""
    selected = selection or os.environ.get("COCHEM_CALCULATION_ENVIRONMENT", "local")
    if selected not in {"github-actions", "local"}:
        raise ValueError("Calculation environment must be github-actions or local")
    return selected


def runtime_environment(
    artifact_dir: Path, calculation_target: str | None = None,
) -> dict[str, str]:
    """Resolve writable runtime locations and reject pollution of the source tree."""
    artifact_dir = artifact_dir.expanduser().resolve()
    if artifact_dir == REPO_ROOT or REPO_ROOT in artifact_dir.parents:
        raise ValueError("The artifact directory must be outside the source checkout")
    selected = calculation_environment(calculation_target)
    env = os.environ.copy()
    env["COCHEM_CALCULATION_ENVIRONMENT"] = selected
    env["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)
    # A hosted profile must never inherit another checkout's execution authority
    # or mutate its scientific silos while auditing this installation.
    registry = (
        artifact_dir / "dashboard" / "actions-interface-no-local-registry.json"
        if selected == "github-actions"
        else artifact_dir / "Registry" / "cochem_system_config.json"
    )
    if selected == "github-actions" and (registry.exists() or registry.is_symlink()):
        raise ValueError("Actions interface cannot adopt any local execution registry")
    env["COCHEM_CONFIG"] = str(registry)
    env["COCHEM_MANIFEST_PATH"] = str(artifact_dir / "dashboard" / "deployment_manifest.json")
    for variable, silo in {
        "COCHEM_CORE_SILO": "cochem_core_silo",
        "COCHEM_UI_SILO": "cochem_ui_silo",
        "COCHEM_CALC_SILO": "cochem_calc_silo",
        "COCHEM_ML_SILO": "cochem_mace_silo",
    }.items():
        env[variable] = str(artifact_dir / "Silos" / silo)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["COCHEM_HEADLESS"] = "1"
    xtb_root = artifact_dir / "free-engines" / "xtb" / "xtb-dist"
    if selected == "github-actions":
        for variable in (
            "XTB_CMD", "COCHEM_XTB_BIN", "XTBPATH", "ORCA_CMD", "COCHEM_ORCA_BIN",
            "CFOUR_CMD", "COCHEM_CFOUR_BIN", "COCHEM_PYSCF_PYTHON",
            "CREST_CMD", "COCHEM_CREST_BIN", "COCHEM_GXTB_BIN", "COCHEM_QE_BIN",
        ):
            env.pop(variable, None)
    elif (xtb_root / "bin" / "xtb").is_file():
        env["XTB_CMD"] = str(xtb_root / "bin" / "xtb")
        env["COCHEM_XTB_BIN"] = env["XTB_CMD"]
        env["XTBPATH"] = str(xtb_root / "share" / "xtb")
        env["PATH"] = str(xtb_root / "bin") + os.pathsep + env.get("PATH", "")
    for variable, directory in {
        "JUPYTER_DATA_DIR": "jupyter-data",
        "JUPYTER_RUNTIME_DIR": "jupyter-runtime",
        "JUPYTER_CONFIG_DIR": "jupyter-config",
        "IPYTHONDIR": "ipython",
        "XDG_CACHE_HOME": "cache",
        "TMPDIR": "scratch",
    }.items():
        path = artifact_dir / "dashboard" / directory
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        env[variable] = str(path)
    return env


def python_path(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def validate_setup(
    python: Path, artifact_dir: Path, calculation_target: str | None = None,
) -> dict:
    """Validate real interface capability or the legacy full local engine authority."""
    selected = calculation_environment(calculation_target)
    environment = runtime_environment(artifact_dir, selected)
    if selected == "github-actions":
        probe = """import importlib.metadata, json, os
from pathlib import Path
import ipykernel, ipywidgets, voila
from ui.voila_layout.cochem_gui import CoChemGUI
registry = Path(os.environ['COCHEM_CONFIG'])
if registry.exists() or registry.is_symlink():
    raise RuntimeError('Actions interface cannot adopt local execution authority')
gui = CoChemGUI()
if gui.calc_env_dropdown.value != 'github-actions':
    raise RuntimeError('The actual GUI did not select its Actions calculation route')
widget = gui.display()
mime = 'application/vnd.jupyter.widget-view+json'
if not isinstance(widget, ipywidgets.VBox) or mime not in widget._repr_mimebundle_():
    raise RuntimeError('The actual interface did not render a Jupyter widget')
if gui.actions_private_panel.layout.display == 'none':
    raise RuntimeError('The private Actions staging panel is unavailable')
if registry.exists() or registry.is_symlink():
    raise RuntimeError('Interface rendering created unexpected execution authority')
print(json.dumps({'status': 'INTERFACE_READY',
    'calculation_environment': 'github-actions',
    'local_execution_authority': False, 'widget_mime': mime,
    'private_staging_panel_visible': True,
    'base_version': importlib.metadata.version('CoChem-BASE'),
    'voila_version': importlib.metadata.version('voila'),
    'scientific_calculation_qualification': False}))
"""
        completed = subprocess.run(
            [str(python), "-c", probe], cwd=REPO_ROOT, env=environment,
            check=True, capture_output=True, text=True, timeout=30,
        )
        return json.loads(completed.stdout)
    probe = """import json
from cochem_base.core.cochem_core_registry_manager import load_system_config
from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.config_loader import resolve_config_path
config = load_system_config(resolve_config_path())
if config.stage0 is None:
    raise RuntimeError('Complete eleven-phase Stage 0 authority is required')
authority = authorize_engine_execution('xtb', cores=1)
print(json.dumps({'status': config.status, 'registry_path': authority.registry_path,
                  'xtb_path': authority.executable, 'xtb_sha256': authority.binary_sha256,
                  'phases': len(config.stage0.phases)}))
"""
    completed = subprocess.run(
        [str(python), "-c", probe], cwd=REPO_ROOT, env=environment,
        check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(completed.stdout)


def setup_dashboard(
    python: Path, artifact_dir: Path, min_disk_space_gb: float,
    calculation_target: str | None = None,
) -> None:
    """Install actual UI/modules; only local mode builds Stage 0 execution authority."""
    selected = calculation_environment(calculation_target)
    env = runtime_environment(artifact_dir, selected)
    subprocess.run([
        sys.executable, str(REPO_ROOT / "scripts/bootstrap_environment.py"),
        "--venv", str(python.parent.parent),
    ], cwd=REPO_ROOT, env=env, check=True)
    # Explicitly refresh the entire UI contract, including newly added plotting
    # dependencies, even when the bootstrap import probe succeeds on an old venv.
    subprocess.run([
        str(python), "-m", "pip", "install", "-e",
        ".[ui,symmetry]" if selected == "github-actions" else ".[dev,symmetry]",
        "-r", "requirements.txt", "-r", "requirements-ui.txt",
    ], cwd=REPO_ROOT, env=env, check=True)
    subprocess.run([str(python), "-m", "pip", "check"], env=env, check=True)
    if selected == "local":
        subprocess.run([
            str(python), str(REPO_ROOT / "scripts/install_free_engines.py"),
            "--root", str(artifact_dir / "free-engines"), "--engines", "xtb",
            "--output", str(artifact_dir / "free-engines" / "installation.json"),
        ], cwd=REPO_ROOT, env=env, check=True)
    manifest = artifact_dir / "dashboard" / "deployment_manifest.json"
    selected_repositories = ["CoChem-BASE"]
    requested_modules = os.environ.get("COCHEM_MODULES", "").replace(",", " ").split()
    if requested_modules:
        catalog = json.loads((REPO_ROOT / "scripts/module-distribution.json").read_text(encoding="utf-8"))["modules"]
        if any(name not in catalog for name in requested_modules):
            raise ValueError("COCHEM_MODULES must contain module IDs from scripts/module-distribution.json")
        subprocess.run([
            str(python), str(REPO_ROOT / "scripts/manage_modules.py"), "install",
            "--modules", *requested_modules, "--root", str(artifact_dir / "Modules"), "--json",
        ], cwd=REPO_ROOT, env=env, check=True)
        selected_repositories.extend(catalog[name]["repository"].split("/")[1]
                                     for name in dict.fromkeys(requested_modules))
    manifest.write_text(json.dumps({"selected_repositories": selected_repositories}) + "\n", encoding="utf-8")
    env = runtime_environment(artifact_dir, selected)
    if selected == "github-actions":
        evidence = validate_setup(python, artifact_dir, selected)
        evidence["scope"] = "Codespaces interface and private Actions job staging"
        evidence["calculation_storage_qualification"] = False
        (artifact_dir / "dashboard" / "setup-validation.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8",
        )
        print("Dashboard interface validated; calculations require their Actions workflow.")
        return
    # Local mode retains its actual xTB and complete eleven-phase Stage 0 gate.
    with (artifact_dir / "dashboard" / "setup-command.json").open("w", encoding="utf-8") as output:
        subprocess.run([
            str(python), str(REPO_ROOT / "cli.py"), "setup", "--all", "--skip-heavy",
            "--artifact-dir", str(artifact_dir), "--min-disk-space-gb", str(min_disk_space_gb), "--json",
        ], cwd=REPO_ROOT, env=env, stdout=output, check=True)
    evidence = validate_setup(python, artifact_dir, selected)
    evidence["min_disk_space_gb"] = min_disk_space_gb
    evidence["scope"] = "BASE dashboard and native xTB CPU screening; optional heavy engines excluded"
    (artifact_dir / "dashboard" / "setup-validation.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8",
    )
    print(f"Dashboard setup validated all {evidence['phases']} phases: {evidence['status']}.")


def page_ready(port: int) -> bool:
    """Require a rendered Voilà response, rather than just an open TCP port."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/", timeout=30) as response:
            content = response.read().decode("utf-8", errors="strict")
            return (
                response.status == 200
                and "jupyter-config-data" in content
                and "application/vnd.jupyter.widget-view+json" in content
                and "CoChem" in content
                and "Traceback" not in content
            )
    except (OSError, UnicodeError, urllib.error.URLError):
        return False


def server_identity(
    python: Path, pid: int, command: list[str],
    expected_environment: dict[str, str] | None = None,
) -> float | None:
    """Return creation time only if this PID runs the exact expected server command.

    The bootstrap interpreter need not contain psutil; the validated UI environment
    does. No unrelated process command line is returned or logged by this probe.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    probe = """import json, psutil, sys
try:
    process = psutil.Process(int(sys.argv[1]))
    expected = json.loads(sys.argv[2])
    required_environment = json.loads(sys.argv[3])
    observed_environment = process.environ() if required_environment else {}
    matching_environment = not required_environment or all(
        observed_environment.get(name) == value
        for name, value in required_environment.items()
    )
    identity = process.create_time() if (
        process.cmdline() == expected and matching_environment
    ) else None
except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
    identity = None
print(json.dumps(identity))
"""
    result = subprocess.run(
        [str(python), "-c", probe, str(pid), json.dumps(command),
         json.dumps(expected_environment or {})],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if result.returncode:
        raise RuntimeError("Could not verify dashboard process identity in its Python environment")
    return json.loads(result.stdout)


def server_command(python: Path, port: int) -> list[str]:
    return [
        str(python), "-m", "voila", str(REPO_ROOT / "Start_Here.ipynb"),
        "--no-browser", f"--port={port}", "--Voila.ip=0.0.0.0",
        "--Voila.port_retries=0",
    ]


def stop_owned_server(child: subprocess.Popen) -> None:
    """Terminate the failed server's session, including kernels, and reap the server."""
    if os.name == "nt":
        if child.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
    else:
        # The server was created with start_new_session=True. Its descendants
        # remain in that group even when Voilà has exited before readiness.
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
    finally:
        if os.name != "nt":
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        child.wait(timeout=5)


def start_dashboard(
    python: Path, artifact_dir: Path, port: int, timeout: float,
    calculation_target: str | None = None,
) -> None:
    selected = calculation_environment(calculation_target)
    env = runtime_environment(artifact_dir, selected)
    expected_environment = {
        name: env[name] for name in ("COCHEM_CONFIG", "COCHEM_CALCULATION_ENVIRONMENT")
    }
    state = artifact_dir / "dashboard" / "server.json"
    if state.exists():
        record = json.loads(state.read_text(encoding="utf-8"))
        identity = server_identity(python, record["pid"], server_command(python, record["port"]), expected_environment)
        if identity is not None and record.get("create_time", identity) == identity:
            if record["port"] == port and page_ready(port):
                # Upgrade records created before process identity was persisted.
                record["create_time"] = identity
                state.write_text(json.dumps(record) + "\n", encoding="utf-8")
                print(f"CoChem dashboard is already ready on port {port}.")
                return
            raise RuntimeError("An existing dashboard process is not ready; inspect its log before restarting")
        # Snapshots preserve files but not processes. A missing, unrelated, or
        # reused PID proves this record is stale; never signal that process.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    log = artifact_dir / "dashboard" / "voila.log"
    command = server_command(python, port)
    with log.open("ab") as output:
        child = subprocess.Popen(
            command, cwd=REPO_ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=(os.name != "nt"),
        )
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline and child.poll() is None:
            if page_ready(port):
                identity = server_identity(python, child.pid, command, expected_environment)
                if identity is None:
                    break
                state.write_text(json.dumps({"pid": child.pid, "port": port, "create_time": identity, "calculation_environment": selected}) + "\n", encoding="utf-8")
                print(f"CoChem dashboard rendered successfully on port {port}.")
                return
            time.sleep(0.25)
    except BaseException:
        stop_owned_server(child)
        raise
    stop_owned_server(child)
    raise RuntimeError(f"Dashboard startup failed; inspect {log}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "start", "check"))
    parser.add_argument("--artifacts", type=Path, default=Path(os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")))
    parser.add_argument("--venv", type=Path)
    parser.add_argument(
        "--calculation-environment", choices=("github-actions", "local"),
        default=os.environ.get("COCHEM_CALCULATION_ENVIRONMENT", "local"),
        help="Actions mode validates the interface without local engine authority",
    )
    parser.add_argument("--port", type=int, default=8866)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--min-disk-space-gb", type=float, default=50.0,
                        help="Minimum free workspace storage; use 1 only for bounded small-molecule acceptance")
    args = parser.parse_args(argv)
    artifacts = args.artifacts.expanduser().resolve()
    runtime_environment(artifacts, args.calculation_environment)
    venv = args.venv.expanduser().resolve() if args.venv else artifacts / "ui-env"
    if venv == REPO_ROOT or REPO_ROOT in venv.parents:
        parser.error("The dashboard virtual environment must be outside the checkout")
    python = python_path(venv)
    if args.command == "setup":
        if args.min_disk_space_gb <= 0:
            parser.error("The minimum workload storage must be positive")
        setup_dashboard(python, artifacts, args.min_disk_space_gb, args.calculation_environment)
    elif args.command == "start":
        if not python.is_file():
            parser.error("Dashboard environment is missing; run the setup command first")
        validate_setup(python, artifacts, args.calculation_environment)
        start_dashboard(python, artifacts, args.port, args.timeout, args.calculation_environment)
    elif not page_ready(args.port):
        print("Dashboard has not rendered successfully", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
