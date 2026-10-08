"""Install and start the Codespaces dashboard with runtime files outside the checkout.

This also provides a locally executable acceptance path for the Codespaces lifecycle.
The forwarded port remains private; production calculations use configured engines.
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

# Matches the reviewed TOPOS release builder. Keep this bootstrap standalone:
# it runs before the BASE package or its scripts namespace is installed.
CONTROLLER_BUILD_TOOLS = {"setuptools": "80.9.0", "wheel": "0.45.1", "build": "1.3.0", "packaging": "25.0"}

REPO_ROOT = Path(__file__).resolve().parent.parent


def runtime_environment(artifact_dir: Path) -> dict[str, str]:
    """Resolve writable runtime locations and reject pollution of the source tree."""
    artifact_dir = artifact_dir.expanduser().resolve()
    if artifact_dir == REPO_ROOT or REPO_ROOT in artifact_dir.parents:
        raise ValueError("The artifact directory must be outside the source checkout")
    env = os.environ.copy()
    env["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)
    # A hosted profile must never inherit another checkout's execution authority
    # or mutate its scientific silos while auditing this installation.
    env["COCHEM_CONFIG"] = str(artifact_dir / "Registry" / "cochem_system_config.json")
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
    if (xtb_root / "bin" / "xtb").is_file():
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


def validate_setup(python: Path, artifact_dir: Path) -> dict:
    """Require current full Stage 0 evidence and actual xTB executable authority."""
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
        [str(python), "-c", probe], cwd=REPO_ROOT, env=runtime_environment(artifact_dir),
        check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(completed.stdout)


def setup_dashboard(python: Path, artifact_dir: Path, min_disk_space_gb: float) -> None:
    """Install the bounded CPU dashboard and publish genuine execution authority."""
    requested_modules = os.environ.get("COCHEM_MODULES", "").replace(",", " ").split()
    kit = os.environ.get("COCHEM_ECOSYSTEM_KIT", "").strip()
    catalog = json.loads((REPO_ROOT / "scripts/module-distribution.json").read_text(encoding="utf-8"))["modules"]
    if any(name not in catalog for name in requested_modules):
        raise ValueError("COCHEM_MODULES must contain module IDs from scripts/module-distribution.json")
    if "topos" in requested_modules and not kit:
        raise ValueError("Set COCHEM_ECOSYSTEM_KIT to the extracted reviewed BASE/TOPOS/TORQ kit")
    env = runtime_environment(artifact_dir)
    subprocess.run([
        sys.executable, str(REPO_ROOT / "scripts/bootstrap_environment.py"),
        "--venv", str(python.parent.parent),
    ], cwd=REPO_ROOT, env=env, check=True)
    # Build the controller with the same exact tools as the reviewed kit.
    # The full installed-wheel metadata/payload checks remain unchanged.
    subprocess.run([str(python), "-m", "pip", "install",
                    *(f"{name}=={version}" for name, version in CONTROLLER_BUILD_TOOLS.items())],
                   cwd=REPO_ROOT, env=env, check=True)
    # Explicitly refresh the entire UI contract, including newly added plotting
    # dependencies, even when the bootstrap import probe succeeds on an old venv.
    subprocess.run([
        str(python), "-m", "pip", "install", "--no-build-isolation", ".[dev,symmetry,ui]",
        "-r", "requirements.txt",
    ], cwd=REPO_ROOT, env=env, check=True)
    subprocess.run([str(python), "-m", "pip", "check"], env=env, check=True)
    subprocess.run([
        str(python), str(REPO_ROOT / "scripts/install_free_engines.py"),
        "--root", str(artifact_dir / "free-engines"), "--engines", "xtb",
        "--output", str(artifact_dir / "free-engines" / "installation.json"),
    ], cwd=REPO_ROOT, env=env, check=True)
    manifest = artifact_dir / "dashboard" / "deployment_manifest.json"
    selected_repositories = ["CoChem-BASE"]
    if requested_modules:
        # TOPOS installs all three mandatory packages in its verified environment.
        # Other module installers retain their independent legacy contract.
        for module in dict.fromkeys(requested_modules):
            command = [str(python), "-I", "-B", "-m", "scripts.manage_modules", "install",
                       "--modules", module, "--root", str(artifact_dir / "Modules"), "--json"]
            if module == "topos":
                command += ["--ecosystem-kit", str(Path(kit).expanduser().resolve(strict=True))]
            subprocess.run(command, cwd=artifact_dir, env=env, check=True)
        selected_repositories.extend(catalog[name]["repository"].split("/")[1]
                                     for name in dict.fromkeys(requested_modules))
    manifest.write_text(json.dumps({"selected_repositories": selected_repositories}) + "\n", encoding="utf-8")
    env = runtime_environment(artifact_dir)  # Include the newly installed binary.
    with (artifact_dir / "dashboard" / "setup-command.json").open("w", encoding="utf-8") as output:
        subprocess.run([
            str(python), str(REPO_ROOT / "cli.py"), "setup", "--all", "--skip-heavy",
            "--artifact-dir", str(artifact_dir), "--min-disk-space-gb", str(min_disk_space_gb), "--json",
        ], cwd=REPO_ROOT, env=env, stdout=output, check=True)
    evidence = validate_setup(python, artifact_dir)
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


def server_identity(python: Path, pid: int, command: list[str]) -> float | None:
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
    identity = process.create_time() if process.cmdline() == expected else None
except (psutil.NoSuchProcess, psutil.ZombieProcess):
    identity = None
print(json.dumps(identity))
"""
    result = subprocess.run(
        [str(python), "-c", probe, str(pid), json.dumps(command)],
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


def start_dashboard(python: Path, artifact_dir: Path, port: int, timeout: float) -> None:
    env = runtime_environment(artifact_dir)
    state = artifact_dir / "dashboard" / "server.json"
    if state.exists():
        record = json.loads(state.read_text(encoding="utf-8"))
        identity = server_identity(python, record["pid"], server_command(python, record["port"]))
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
                identity = server_identity(python, child.pid, command)
                if identity is None:
                    break
                state.write_text(json.dumps({"pid": child.pid, "port": port, "create_time": identity}) + "\n", encoding="utf-8")
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
    parser.add_argument("--port", type=int, default=8866)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--min-disk-space-gb", type=float, default=50.0,
                        help="Minimum free workspace storage; use 1 only for bounded small-molecule acceptance")
    args = parser.parse_args(argv)
    artifacts = args.artifacts.expanduser().resolve()
    runtime_environment(artifacts)
    venv = args.venv.expanduser().resolve() if args.venv else artifacts / "ui-env"
    if venv == REPO_ROOT or REPO_ROOT in venv.parents:
        parser.error("The dashboard virtual environment must be outside the checkout")
    python = python_path(venv)
    if args.command == "setup":
        if args.min_disk_space_gb <= 0:
            parser.error("The minimum workload storage must be positive")
        setup_dashboard(python, artifacts, args.min_disk_space_gb)
    elif args.command == "start":
        if not python.is_file():
            parser.error("Dashboard environment is missing; run the setup command first")
        validate_setup(python, artifacts)
        start_dashboard(python, artifacts, args.port, args.timeout)
    elif not page_ready(args.port):
        print("Dashboard has not rendered successfully", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
