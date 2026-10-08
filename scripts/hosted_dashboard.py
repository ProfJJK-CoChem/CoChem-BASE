"""Install and start the Codespaces dashboard with runtime files outside the checkout.

This also provides a locally executable acceptance path for the Codespaces lifecycle.
The forwarded port remains private; production calculations use configured engines.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def assignment_identity(source: Path) -> dict[str, str]:
    """Discover a student's actual repository without displaying remote credentials."""
    result = subprocess.run(["git", "-C", str(source), "config", "--get", "remote.origin.url"],
        capture_output=True, text=True, check=False, timeout=15)
    url = result.stdout.strip()
    repository = None
    if result.returncode == 0 and len(url) <= 4096:
        if url.startswith("git@github.com:"):
            repository = url[len("git@github.com:"):]
        else:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme in {"https", "ssh"} and parsed.hostname == "github.com":
                repository = parsed.path.lstrip("/")
        if repository and repository.endswith(".git"):
            repository = repository[:-4]
    if not repository or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repository):
        return {}
    branch = subprocess.run(["git", "-C", str(source), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True, text=True, check=False, timeout=15)
    name = branch.stdout.strip().removeprefix("origin/") if branch.returncode == 0 else ""
    if not name:
        branch = subprocess.run(["git", "-C", str(source), "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, check=False, timeout=15)
        name = branch.stdout.strip() if branch.returncode == 0 else "main"
    return {"GITHUB_REPOSITORY": repository, "GITHUB_REF_NAME": name}


def runtime_environment(artifact_dir: Path) -> dict[str, str]:
    """Resolve writable runtime locations and reject pollution of the source tree."""
    artifact_dir = artifact_dir.expanduser().resolve()
    if artifact_dir == REPO_ROOT or REPO_ROOT in artifact_dir.parents:
        raise ValueError("The artifact directory must be outside the source checkout")
    env = os.environ.copy()
    try:
        from scripts.setup_licensed_engines import load_environment
    except ModuleNotFoundError as error:
        if error.name != "scripts":
            raise
        from setup_licensed_engines import load_environment
    licensed_values, licensed_paths = load_environment(artifact_dir)
    env.update(licensed_values)
    if licensed_paths:
        env["PATH"] = os.pathsep.join([*licensed_paths, env.get("PATH", "")])
    env["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)
    origin_record = artifact_dir / "StudentSetup" / "assignment-runtime.json"
    if origin_record.is_file():
        origin = json.loads(origin_record.read_text(encoding="utf-8"))
        env["COCHEM_ASSIGNMENT_ROOT"] = origin["source_path"]
    else:
        env["COCHEM_ASSIGNMENT_ROOT"] = str(REPO_ROOT)
    identity = assignment_identity(Path(env["COCHEM_ASSIGNMENT_ROOT"]))
    if identity:
        # Actions already supplies authoritative values for that same checkout;
        # an external interface runtime must never substitute its own BASE repo.
        if env.get("GITHUB_REPOSITORY") != identity["GITHUB_REPOSITORY"]:
            env.update(identity)
        elif not env.get("GITHUB_REF_NAME"):
            env["GITHUB_REF_NAME"] = identity["GITHUB_REF_NAME"]
    authority_dir = artifact_dir
    active_path = artifact_dir / "StudentSetup" / "active-runtime.json"
    if active_path.is_file():
        active = json.loads(active_path.read_text(encoding="utf-8"))
        if active.get("kind") == "reviewed-release":
            _validate_runtime_metadata(active, artifact_dir)
            authority_dir = Path(active["authority_path"])
    # A hosted profile must never inherit another checkout's execution authority
    # or mutate its scientific silos while auditing this installation.
    env["COCHEM_CONFIG"] = str(authority_dir / "Registry" / "cochem_system_config.json")
    env["COCHEM_MANIFEST_PATH"] = str(authority_dir / "dashboard" / "deployment_manifest.json")
    for variable, silo in {
        "COCHEM_CORE_SILO": "cochem_core_silo",
        "COCHEM_UI_SILO": "cochem_ui_silo",
        "COCHEM_CALC_SILO": "cochem_calc_silo",
        "COCHEM_ML_SILO": "cochem_mace_silo",
    }.items():
        env[variable] = str(authority_dir / "Silos" / silo)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["COCHEM_HEADLESS"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for relative in ("free-engines", "free-engines/downloads", "free-engines/xtb/xtb-dist", "free-engines/crest/crest", "free-engines/native"):
        owned = artifact_dir / relative
        if owned.is_symlink() or not owned.resolve().is_relative_to(artifact_dir):
            raise ValueError("Free-engine runtime files must remain inside their external profile")
    free_status_path = artifact_dir / "free-engines/setup-status.json"
    if free_status_path.is_symlink() or (free_status_path.is_file() and free_status_path.stat().st_size > 4 * 1024 * 1024):
        raise ValueError("Free-engine setup status is redirected or exceeds its size budget")
    free_status = json.loads(free_status_path.read_text(encoding="utf-8")) if free_status_path.is_file() else {}
    failed_engines = {name for name, record in free_status.get("engines", {}).items()
                      if record.get("status") == "failed"}
    for name in failed_engines:
        owned = artifact_dir / "free-engines"
        variables = ("XTB_CMD", "COCHEM_XTB_BIN", "XTBPATH") if name == "xtb" else ("CREST_CMD", "COCHEM_CREST_BIN")
        for variable in variables:
            if env.get(variable) and Path(env[variable]).expanduser().absolute().is_relative_to(owned):
                env.pop(variable)
        env["PATH"] = os.pathsep.join(entry for entry in env.get("PATH", "").split(os.pathsep)
            if not Path(entry).expanduser().absolute().is_relative_to(owned / name)
            and not Path(entry).expanduser().absolute().is_relative_to(owned / "native"))
    xtb_root = artifact_dir / "free-engines" / "xtb" / "xtb-dist"
    if "xtb" not in failed_engines and (xtb_root / "bin" / "xtb").is_file():
        env["XTB_CMD"] = str(xtb_root / "bin" / "xtb")
        env["COCHEM_XTB_BIN"] = env["XTB_CMD"]
        env["XTBPATH"] = str(xtb_root / "share" / "xtb")
        env["PATH"] = str(xtb_root / "bin") + os.pathsep + env.get("PATH", "")
    crest = artifact_dir / "free-engines/crest/crest/crest"
    if "crest" not in failed_engines and crest.is_file():
        env["CREST_CMD"] = str(crest)
        env["COCHEM_CREST_BIN"] = str(crest)
    native_root = artifact_dir / "free-engines/native"
    if not failed_engines and (native_root / "installation.json").is_file():
        try:
            from scripts.install_native_free_engines import verify_native_runtime
        except ModuleNotFoundError:
            from install_native_free_engines import verify_native_runtime
        native = verify_native_runtime(native_root)
        prefix = Path(native["prefix"])
        env.update(XTB_CMD=native["engines"]["xtb"]["path"],
            COCHEM_XTB_BIN=native["engines"]["xtb"]["path"],
            CREST_CMD=native["engines"]["crest"]["path"],
            COCHEM_CREST_BIN=native["engines"]["crest"]["path"], XTBPATH=str(prefix / "share/xtb"))
        env["PATH"] = str(prefix / "bin") + os.pathsep + env.get("PATH", "")
    for variable, directory in {
        "JUPYTER_DATA_DIR": "jupyter-data",
        "JUPYTER_RUNTIME_DIR": "jupyter-runtime",
        "JUPYTER_CONFIG_DIR": "jupyter-config",
        "IPYTHONDIR": "ipython",
        "XDG_CACHE_HOME": "cache",
        "TMPDIR": "scratch",
    }.items():
        path = artifact_dir / "dashboard" / directory
        if not path.resolve().is_relative_to(artifact_dir):
            raise ValueError("Dashboard runtime directories must remain inside the external artifact directory")
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        env[variable] = str(path)
    return env


def prepare_free_engines(python: Path, artifact_dir: Path, *, environment: dict[str, str] | None = None) -> dict:
    """Keep BASE ingestion usable when a genuine free-engine download fails."""
    import platform
    try:
        from scripts.manage_modules import _atomic_json, _redact
    except ModuleNotFoundError:
        from manage_modules import _atomic_json, _redact
    runtime = runtime_environment(artifact_dir)
    env = setup_build_environment(runtime if environment is None else {**runtime, **environment})
    engines = {}
    if platform.system() == "Linux" and platform.machine() in {"x86_64", "AMD64"}:
        commands = [(name, [str(python), str(REPO_ROOT / "scripts/install_free_engines.py"),
            "--root", str(artifact_dir / "free-engines"), "--engines", name,
            "--output", str(artifact_dir / f"free-engines/{name}-installation.json")]) for name in ("xtb", "crest")]
    elif platform.system() == "Darwin":
        commands = [("native", [str(python), str(REPO_ROOT / "scripts/install_native_free_engines.py"),
            "--root", str(artifact_dir / "free-engines/native")])]
    else:
        commands = []
    for name, command in commands:
        names = ("xtb", "crest") if name == "native" else (name,)
        try:
            completed = subprocess.run(command, cwd=REPO_ROOT, env=env, check=True,
                capture_output=True, text=True, timeout=1200)
            if name == "native":
                observed = json.loads(completed.stdout)["engines"]
            else:
                observed = json.loads((artifact_dir / f"free-engines/{name}-installation.json").read_text())["engines"]
            for engine in names:
                record = observed[engine]
                engines[engine] = {"status": "installed", "version": record["version"], "path": record["path"],
                    "message": "Pinned package integrity and actual executable version verified."}
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            message = _redact((getattr(error, "stderr", "") or str(error))[-2000:])
            for engine in names:
                engines[engine] = {"status": "failed", "message": message,
                    "scientific_execution_verified": False}
    failed = any(record["status"] == "failed" for record in engines.values())
    result = {"schema_version": "cochem.free-engine-setup/1", "status": "failed" if failed else ("ready" if engines else "not_applicable"),
        "engines": engines, "message": "BASE remains available. Unavailable free-engine methods are disabled; choose Retry setup to retry downloads and refresh execution authority." if failed else
        ("Pinned free-engine installations verified." if engines else "Local free-engine binaries are not available for this host; supported remote calculation routes remain available.")}
    _atomic_json(artifact_dir / "free-engines/setup-status.json", result)
    return result


def python_path(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def configure_student_workspace(artifact_dir: Path) -> dict:
    """Show the owned ingestion inbox in VS Code without changing SOURCE."""
    env = runtime_environment(artifact_dir)
    inbox = artifact_dir / "Input_Files/Inbox"
    if inbox.is_symlink() or not inbox.resolve().is_relative_to(artifact_dir.resolve()):
        raise ValueError("The student inbox must remain inside the external artifact directory")
    inbox.mkdir(parents=True, exist_ok=True, mode=0o750)
    workspace = artifact_dir / "dashboard/CoChem.code-workspace"
    receipt = artifact_dir / "dashboard/student-workspace.json"
    if workspace.is_symlink() or receipt.is_symlink():
        raise ValueError("Student workspace records may not redirect to another file")
    workspace.write_text(json.dumps({"folders": [
        {"name": "CoChem-BASE", "path": env["COCHEM_ASSIGNMENT_ROOT"]},
        {"name": "Student input inbox", "path": str(inbox)},
    ]}, indent=2) + "\n", encoding="utf-8")
    executable = shutil.which("code")
    record = {"schema_version": "cochem.student-workspace/1", "inbox": str(inbox), "workspace": str(workspace)}
    if executable:
        result = subprocess.run([executable, "--add", str(inbox)], env=setup_build_environment(env),
            capture_output=True, text=True, timeout=30, check=False)
        record["status"] = "attached" if result.returncode == 0 else "workspace_saved"
        record["editor_exit_code"] = result.returncode
    else:
        record["status"] = "workspace_saved"
    receipt.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return record


def validate_setup(python: Path, artifact_dir: Path) -> dict:
    """Require full Stage 0 and report only genuinely authorized free engines."""
    probe = """import json
from cochem_base.core.cochem_core_registry_manager import load_system_config
from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.config_loader import resolve_config_path
config = load_system_config(resolve_config_path())
if config.stage0 is None or len(config.stage0.phases) != 11:
    raise RuntimeError('Complete eleven-phase Stage 0 authority is required')
if config.status not in {'LOCKED','ACTIVE','PASSED','DEGRADED_OPERATIONAL'} or not config.verify_checksum():
    raise RuntimeError('Stage 0 did not publish a verified operational Golden Registry')
engines={}
for name in ('xtb','crest','pyscf'):
    record=config.model_dump(mode='json').get('engines',{}).get(name,{})
    if record.get('status') in {'found','ready'}:
        authority=authorize_engine_execution(name,cores=1)
        engines[name]={'path':authority.executable,'sha256':authority.binary_sha256}
print(json.dumps({'status':config.status,'registry_path':str(resolve_config_path()),
    'xtb_path':engines.get('xtb',{}).get('path'),'xtb_sha256':engines.get('xtb',{}).get('sha256'),
    'engines':engines,'phases':len(config.stage0.phases)}))
"""
    completed = subprocess.run(
        [str(python), "-B", "-c", probe], cwd=REPO_ROOT, env=runtime_environment(artifact_dir),
        check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(completed.stdout)


def setup_build_environment(env: dict[str, str]) -> dict[str, str]:
    """Source/binary credentials never reach bootstrap or package build hooks."""
    result = {key: value for key, value in env.items() if not key.startswith("GIT_")
              and key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "SSH_ASKPASS"}
              and not any(word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTHORIZATION"))
              and not key.upper().endswith("_KEY")}
    result.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
                  PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    return result


def requested_silos(artifact_dir: Path) -> list[str]:
    """Preserve explicit optional ML choices and provision supported CPU science."""
    names = {"cochem_core_silo", "cochem_ui_silo", "cochem_calc_silo", "cochem_mace_silo"}
    configured = os.environ.get("COCHEM_REQUESTED_SILOS")
    if configured:
        selected = configured.replace(",", " ").split()
    else:
        manifest = Path(runtime_environment(artifact_dir)["COCHEM_MANIFEST_PATH"])
        previous = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
        selected = previous.get("requested_silos")
        if selected is None:
            selected = ["cochem_core_silo", "cochem_ui_silo"]
            if os.name != "nt":
                selected.append("cochem_calc_silo")
    if (not isinstance(selected, list) or not all(isinstance(name, str) and name in names for name in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("Only the four reviewed micro-silo identities may be selected.")
    return sorted(set(selected) | {"cochem_core_silo", "cochem_ui_silo"})


def setup_dashboard(python: Path, artifact_dir: Path, min_disk_space_gb: float) -> None:
    """Install the bounded CPU dashboard and publish genuine execution authority."""
    env = runtime_environment(artifact_dir)
    build_env = setup_build_environment(env)
    subprocess.run([
        sys.executable, str(REPO_ROOT / "scripts/bootstrap_environment.py"),
        "--venv", str(python.parent.parent),
    ], cwd=REPO_ROOT, env=build_env, check=True)
    # Explicitly refresh the entire UI contract, including newly added plotting
    # dependencies, even when the bootstrap import probe succeeds on an old venv.
    subprocess.run([
        str(python), "-m", "pip", "install", "-e", ".[dev,symmetry]",
        "-r", "requirements.txt", "-r", "requirements-ui.txt",
    ], cwd=REPO_ROOT, env=build_env, check=True)
    subprocess.run([str(python), "-m", "pip", "check"], env=build_env, check=True)
    free_engines = prepare_free_engines(python, artifact_dir)
    if free_engines["status"] == "failed":
        print(free_engines["message"])
    manifest = artifact_dir / "dashboard" / "deployment_manifest.json"
    selected_repositories = ["CoChem-BASE"]
    requested_modules = os.environ.get("COCHEM_MODULES", "").replace(",", " ").split()
    automatic = (os.environ.get("CODESPACES", "").lower() == "true"
                 or os.environ.get("COCHEM_STUDENT_AUTO_SETUP", "").lower() == "true")
    if automatic and not requested_modules:
        requested_modules = ["topos", "torq"]
    if requested_modules:
        catalog = json.loads((REPO_ROOT / "scripts/module-distribution.json").read_text(encoding="utf-8"))["modules"]
        if any(name not in catalog for name in requested_modules):
            raise ValueError("COCHEM_MODULES must contain module IDs from scripts/module-distribution.json")
        # A provider access/build failure must disable that provider rather than
        # prevent students from opening BASE and fixing access using Retry setup.
        probe = """import json,sys
from cochem_base.interfaces.student_setup import StudentSetupService
service=StudentSetupService(sys.argv[1],sys.argv[2])
result=service.install_modules(json.loads(sys.argv[3]))
print(json.dumps(result))
"""
        try:
            completed = subprocess.run([str(python), "-B", "-c", probe, str(artifact_dir), str(REPO_ROOT), json.dumps(requested_modules)],
                cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False, timeout=3600)
        except subprocess.TimeoutExpired:
            completed = subprocess.CompletedProcess([], 1, stdout="", stderr="Optional module setup exceeded its setup budget. Retry setup from the interface.")
        if completed.returncode == 0:
            result = json.loads(completed.stdout)
            selected_repositories.extend(catalog[name]["repository"].split("/")[1]
                for name, item in result["modules"].items() if item["status"] == "installed")
        else:
            # Preserve bounded diagnostics for the GUI; never print a credential.
            try:
                from scripts.manage_modules import _atomic_json, _redact
            except ModuleNotFoundError:
                from manage_modules import _atomic_json, _redact
            setup_dir = artifact_dir / "StudentSetup"
            setup_dir.mkdir(exist_ok=True, mode=0o700)
            _atomic_json(setup_dir / "initial-setup.json", {"schema_version": "cochem.student-setup/1", "ready": False,
                "modules": {name: {"status": "failed", "operations": [], "message": _redact(completed.stderr[-4000:])}
                            for name in requested_modules}})
        print("Optional module setup completed; unavailable modules can be retried in the interface.")
    manifest.write_text(json.dumps({"selected_repositories": selected_repositories,
        "requested_silos": requested_silos(artifact_dir)}) + "\n", encoding="utf-8")
    refresh_stage0_authority(python, artifact_dir, min_disk_space_gb)


def refresh_stage0_authority(python: Path, artifact_dir: Path, min_disk_space_gb: float = 1.0) -> dict:
    """Publish fresh complete authority after a genuine engine setup or retry."""
    env = runtime_environment(artifact_dir)  # Include the newly installed binary.
    authority = Path(env["COCHEM_CONFIG"]).parent.parent
    with (artifact_dir / "dashboard" / "setup-command.json").open("w", encoding="utf-8") as output:
        subprocess.run([
            str(python), str(REPO_ROOT / "cli.py"), "setup", "--all",
            "--artifact-dir", str(authority), "--min-disk-space-gb", str(min_disk_space_gb), "--json",
        ], cwd=REPO_ROOT, env=setup_build_environment(env), stdout=output, check=True)
    evidence = validate_setup(python, artifact_dir)
    evidence["min_disk_space_gb"] = min_disk_space_gb
    evidence["scope"] = "BASE dashboard with full Stage 0 and supported native CPU science; optional ML is provisioned only when selected"
    (artifact_dir / "dashboard" / "setup-validation.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8",
    )
    print(f"Dashboard setup validated all {evidence['phases']} phases: {evidence['status']}.")
    return evidence


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
        [str(python), "-B", "-c", probe, str(pid), json.dumps(command)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if result.returncode:
        raise RuntimeError("Could not verify dashboard process identity in its Python environment")
    return json.loads(result.stdout)


def server_command(python: Path, port: int, source_root: Path | None = None) -> list[str]:
    source = source_root or REPO_ROOT
    return [
        str(python), "-B", str(source / "scripts/student_voila.py"), str(source / "Start_Here.ipynb"),
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
                record["command"] = server_command(python, port)
                state.write_text(json.dumps(record) + "\n", encoding="utf-8")
                print(f"CoChem dashboard is already ready on port {port}.")
                return
            raise RuntimeError("An existing dashboard process is not ready; inspect its log before restarting")
        # Snapshots preserve files but not processes. A missing, unrelated, or
        # reused PID proves this record is stale; never signal that process.
    with socket.socket() as probe:
        # A managed restart can follow authenticated browser requests while
        # the old listener's connections remain in TIME_WAIT. A live listener
        # still prevents this bind; do not require students to wait or retry.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
                state.write_text(json.dumps({"pid": child.pid, "port": port, "create_time": identity, "command": command}) + "\n", encoding="utf-8")
                print(f"CoChem dashboard rendered successfully on port {port}.")
                return
            time.sleep(0.25)
    except BaseException:
        stop_owned_server(child)
        raise
    stop_owned_server(child)
    raise RuntimeError(f"Dashboard startup failed; inspect {log}")


def _validate_runtime_metadata(record: dict, artifact_dir: Path) -> None:
    """Validate paths using only stdlib before selecting an environment."""
    if not isinstance(record, dict) or record.get("schema_version") != "cochem.student-runtime/1":
        raise RuntimeError("The selected runtime has no valid versioned receipt")
    source = Path(record.get("source_path", "")).resolve()
    python = Path(record.get("python_path", "")).absolute()
    if record.get("kind") == "reviewed-release":
        import re
        revision = record.get("revision", "")
        if not re.fullmatch(r"[0-9a-f]{40}", str(revision)):
            raise RuntimeError("The selected runtime has no immutable Git identity")
        spec = record.get("base_spec", {})
        if spec.get("repository") != "ProfJJK-CoChem/CoChem-BASE" or spec.get("revision") != revision:
            raise RuntimeError("The selected runtime has an invalid upstream identity")
        from scripts.manage_modules import _paths

        try:
            location = _paths("base", spec, artifact_dir / "BaseRuntime")[1]
        except ValueError as error:
            raise RuntimeError("The selected runtime is outside its managed revision") from error
        if source != location / "source" or python != python_path(location / "env"):
            raise RuntimeError("The selected runtime is outside its managed revision")
        if Path(record.get("authority_path", "")).resolve() != location / "authority":
            raise RuntimeError("The selected authority is outside its managed revision")
    elif record.get("kind") == "assignment":
        origin_path = artifact_dir / "StudentSetup/assignment-runtime.json"
        origin = json.loads(origin_path.read_text(encoding="utf-8")) if origin_path.is_file() else None
        expected = Path(origin["source_path"]).resolve() if origin else REPO_ROOT
        if source != expected or not (source / "Start_Here.ipynb").is_file() or not python.is_file():
            raise RuntimeError("The assignment runtime is unavailable")
    else:
        raise RuntimeError("The selected runtime kind is unsupported")


def selected_runtime(artifact_dir: Path) -> dict | None:
    """Resolve external code only after trusted BASE verifies its source/env."""
    state = artifact_dir / "StudentSetup" / "active-runtime.json"
    if not state.exists():
        return None
    record = json.loads(state.read_text(encoding="utf-8"))
    _validate_runtime_metadata(record, artifact_dir)
    if record.get("kind") == "reviewed-release":
        # The devcontainer's bootstrap interpreter has no scientific/UI packages.
        # Verify with the original BASE environment before executing the target.
        verifier = python_path(artifact_dir / "ui-env")
        if not verifier.is_file():
            raise RuntimeError("The original BASE verifier environment is unavailable")
        probe = """import json,sys
from pathlib import Path
from scripts.manage_modules import verify_installation
record=json.loads(sys.argv[1])
verify_installation('base',record['base_spec'],Path(sys.argv[2])/'BaseRuntime',active=False)
"""
        env = runtime_environment(artifact_dir)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([str(verifier), "-B", "-c", probe, json.dumps(record), str(artifact_dir)],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError("The selected BASE source or environment failed integrity verification; the previous runtime has been retained")
    return record


def stop_dashboard(python: Path, artifact_dir: Path) -> None:
    """Stop only an exact recorded dashboard identity, including its kernels."""
    state = artifact_dir / "dashboard" / "server.json"
    if not state.is_file():
        return
    record = json.loads(state.read_text(encoding="utf-8"))
    origin_path = artifact_dir / "StudentSetup" / "assignment-runtime.json"
    origin = json.loads(origin_path.read_text(encoding="utf-8")) if origin_path.is_file() else None
    candidates = [server_command(python, record["port"])]
    if origin is not None:
        candidates.append(server_command(Path(origin["python_path"]), record["port"], Path(origin["source_path"])))
    # Retained history proves an older external runtime's expected exact launch
    # command after another version has been selected, without trusting arbitrary
    # command strings placed in server.json.
    history = artifact_dir / "StudentSetup" / "history"
    if history.is_dir():
        for path in history.glob("*.json"):
            runtime = json.loads(path.read_text(encoding="utf-8"))["runtime"]
            _validate_runtime_metadata(runtime, artifact_dir)
            candidates.append(server_command(Path(runtime["python_path"]), record["port"], Path(runtime["source_path"])))
    last_update = artifact_dir / "StudentSetup" / "last-update.json"
    if last_update.is_file():
        previous_running = json.loads(last_update.read_text(encoding="utf-8")).get("runtime")
        if previous_running is not None:
            _validate_runtime_metadata(previous_running, artifact_dir)
            candidates.append(server_command(Path(previous_running["python_path"]), record["port"], Path(previous_running["source_path"])))
    # Retained servers from before authenticated XSRF-cookie initialization used
    # upstream's module entry point. The source/interpreter paths remain fixed.
    candidates += [[*candidate[:2], "-m", "voila", *candidate[3:]] for candidate in list(candidates)]
    # Upgrade servers launched before immutable runtime bytecode suppression.
    # Every legacy variant still has the same verified source/interpreter paths.
    candidates += [[argument for argument in candidate if argument != "-B"] for candidate in list(candidates)]
    command = record.get("command")
    if command is None:
        command = next((candidate for candidate in candidates
                        if server_identity(python, record["pid"], candidate) is not None), None)
    if command not in candidates:
        raise RuntimeError("The recorded dashboard command is outside the managed runtime; no process was stopped")
    identity = server_identity(python, record["pid"], command)
    if identity is None:
        state.unlink(missing_ok=True)
        return
    if record.get("create_time", identity) != identity:
        raise RuntimeError("The dashboard PID identity changed; no process was stopped")
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(record["pid"]), "/T", "/F"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        if os.getpgid(record["pid"]) != record["pid"]:
            raise RuntimeError("The dashboard is not in its owned process session; no process was stopped")
        os.killpg(record["pid"], signal.SIGTERM)
        deadline = time.monotonic() + 10
        while server_identity(python, record["pid"], command) is not None and time.monotonic() < deadline:
            time.sleep(0.2)
        try:
            os.killpg(record["pid"], signal.SIGKILL)
        except ProcessLookupError:
            pass
    state.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "start", "check", "restart", "stop", "workspace"))
    parser.add_argument("--artifacts", type=Path, default=Path(os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")))
    parser.add_argument("--venv", type=Path)
    parser.add_argument("--port", type=int, default=8866)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--restart-delay", type=float, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--min-disk-space-gb", type=float, default=50.0,
                        help="Minimum free workspace storage; use 1 only for bounded small-molecule acceptance")
    args = parser.parse_args(argv)
    artifacts = args.artifacts.expanduser().resolve()
    env = runtime_environment(artifacts)
    if args.command == "workspace":
        print(json.dumps(configure_student_workspace(artifacts)))
        return 0
    if args.restart_delay < 0 or args.restart_delay > 5:
        parser.error("Restart delay must be between zero and five seconds")
    if args.restart_delay:
        time.sleep(args.restart_delay)
    runtime = selected_runtime(artifacts) if args.command != "setup" else None
    if runtime is not None and Path(runtime["source_path"]).resolve() != REPO_ROOT:
        source = Path(runtime["source_path"])
        command = [runtime["python_path"], str(source / "scripts/hosted_dashboard.py"), args.command,
                   "--artifacts", str(artifacts), "--port", str(args.port), "--timeout", str(args.timeout)]
        return subprocess.call(command, cwd=source, env=env)
    venv = args.venv.expanduser().resolve() if args.venv else artifacts / "ui-env"
    if venv == REPO_ROOT or REPO_ROOT in venv.parents:
        parser.error("The dashboard virtual environment must be outside the checkout")
    python = Path(runtime["python_path"]) if runtime is not None else python_path(venv)
    if args.command == "setup":
        if args.min_disk_space_gb <= 0:
            parser.error("The minimum workload storage must be positive")
        setup_dashboard(python, artifacts, args.min_disk_space_gb)
    elif args.command in {"restart", "stop"}:
        stop_dashboard(python, artifacts)
        if args.command == "restart":
            validate_setup(python, artifacts)
            start_dashboard(python, artifacts, args.port, args.timeout)
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
