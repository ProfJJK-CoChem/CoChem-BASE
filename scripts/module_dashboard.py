"""Launch the complete installed TOPOS interface from BASE's verified module kit.

The browser uses the same authenticated registry and scientific workflow as the
typed module receiver. Launching the interface neither installs licensed engines
nor certifies calculations. The process is owned by the caller and stops when
the foreground CLI or BASE GUI stops it.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import psutil

from scripts import manage_modules as manager

_PROBE = """import json, pathlib, sys
import topos.ui
from streamlit.testing.v1 import AppTest
prefix = pathlib.Path(sys.prefix).resolve()
application = pathlib.Path(topos.ui.__file__).resolve().with_name('streamlit_app.py')
if not application.is_relative_to(prefix) or not application.is_file():
    raise RuntimeError('The TOPOS dashboard must belong to the installed isolated environment')
rendered = AppTest.from_file(str(application)).run(timeout=60)
if rendered.exception:
    raise RuntimeError('The installed TOPOS dashboard failed its initial rendering: ' +
                       '; '.join(str(item.message) for item in rendered.exception))
if not rendered.title or rendered.title[0].value != 'CoChem-TOPOS 0.1.0':
    raise RuntimeError('The installed TOPOS dashboard did not render its expected application')
print(json.dumps({'application': str(application), 'title': rendered.title[0].value}))
"""


def browser_url(port: int, environment: dict[str, str] | None = None) -> str:
    """Use the student's private Codespaces forwarding host when available."""
    values = os.environ if environment is None else environment
    name = values.get("CODESPACE_NAME", "")
    domain = values.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "")
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) and re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", domain):
        return f"https://{name}-{port}.{domain}"
    return f"http://127.0.0.1:{port}"


def dashboard_environment(runtime: Path, output: Path, inherited: dict[str, str] | None = None,
                          *, remote_repository: str | None = None, remote_ref: str = "main",
                          base_commit: str | None = None) -> dict[str, str]:
    """Bind installed authority; only account authentication reaches the controller.

    GitHub account authentication belongs to the UI control plane. TOPOS's BASE
    adapter separately strips it from every native scientific child process.
    Archive/source credentials and arbitrary source/config overrides are removed.
    """
    from scripts.setup_licensed_engines import load_environment

    values = dict(os.environ if inherited is None else inherited)
    excluded = {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV", "GIT_ASKPASS", "SSH_ASKPASS"}
    environment = {key: value for key, value in values.items()
                   if key not in excluded and not key.startswith(("GIT_", "LD_", "DYLD_", "COCHEM_", "COCH_", "TOPOS_"))
                   and not any(word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTHORIZATION"))
                   and not key.upper().endswith("_KEY")}
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        if key in values:
            environment[key] = values[key]
    mode = values.get("COCHEM_PRIVATE_GH_AUTH", "auto")
    if mode not in {"auto", "stored-cli", "environment"}:
        raise ValueError("COCHEM_PRIVATE_GH_AUTH must be auto, stored-cli, or environment")
    environment["COCHEM_PRIVATE_GH_AUTH"] = mode
    if remote_repository is not None:
        if not manager.REPOSITORY_PATTERN.fullmatch(remote_repository):
            raise ValueError("The remote controller must be an explicit OWNER/REPOSITORY")
        if not isinstance(remote_ref, str) or not remote_ref or any(ord(char) < 33 for char in remote_ref):
            raise ValueError("The remote controller ref must be explicit and contain no whitespace")
        if not isinstance(base_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", base_commit):
            raise ValueError("Remote BASE execution must bind to the installed kit's exact source commit")
    runtime = runtime.expanduser().resolve(strict=True)
    output = output.expanduser().resolve(strict=True)
    environment.update(COCHEM_ARTIFACT_DIR=str(runtime),
                       COCHEM_CONFIG=str(runtime / "Registry/cochem_system_config.json"),
                       COCHEM_MANIFEST_PATH=str(runtime / "mandatory-deployment.json"),
                       TOPOS_EXECUTION_BACKEND="base", TOPOS_OUTPUT_ROOT=str(output / "runs"),
                       PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
                       COCHEM_HEADLESS="1", QT_QPA_PLATFORM="offscreen")
    for variable, directory in {"COCHEM_CORE_SILO": "cochem_core_silo", "COCHEM_UI_SILO": "cochem_ui_silo",
                                "COCHEM_CALC_SILO": "cochem_calc_silo", "COCHEM_ML_SILO": "cochem_mace_silo"}.items():
        environment[variable] = str(runtime / "Silos" / directory)
    licensed_values, licensed_paths = load_environment(runtime)
    environment.update(licensed_values)
    if licensed_paths:
        environment["PATH"] = os.pathsep.join([*licensed_paths, environment.get("PATH", "")])
    for variable, directory in {"XDG_CACHE_HOME": "cache", "TMPDIR": "scratch"}.items():
        folder = output / directory
        folder.mkdir(mode=0o700, exist_ok=True)
        environment[variable] = str(folder)
    settings = output / "topos-settings.json"
    configuration = {"execution_backend": "base", "base_registry_path": environment["COCHEM_CONFIG"],
                     "output_root": environment["TOPOS_OUTPUT_ROOT"]}
    if remote_repository is not None:
        configuration.update(remote_repository=remote_repository, remote_ref=remote_ref, remote_base_commit=base_commit)
    manager._atomic_json(settings, configuration)
    environment["TOPOS_CONFIG"] = str(settings)
    return environment


def page_ready(port: int) -> bool:
    """Check the actual Streamlit HTTP service after the installed render probe."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as response:
            if response.status != 200 or response.read(1024).strip() != b"ok":
                return False
        with opener.open(f"http://127.0.0.1:{port}/", timeout=2) as response:
            return response.status == 200 and b"Streamlit" in response.read(1024 * 1024)
    except (OSError, urllib.error.URLError):
        return False


def owns_listener(process: psutil.Process, port: int) -> bool:
    """Reject a healthy unrelated server which acquired the port during startup."""
    try:
        return any(connection.status == psutil.CONN_LISTEN
                   and connection.laddr.ip == "127.0.0.1" and connection.laddr.port == port
                   for connection in process.net_connections(kind="tcp"))
    except psutil.NoSuchProcess:
        return False


@dataclass
class ModuleDashboard:
    """A live process handle; never reconstruct ownership from a saved PID."""

    process: subprocess.Popen
    port: int
    output: Path
    revision: str
    command: list[str]
    create_time: float
    url: str
    stopped: bool = False

    def stop(self) -> None:
        """Stop the owned server and its native child jobs, then reap the launcher."""
        from scripts.hosted_dashboard import stop_owned_server

        if self.stopped:
            return
        descendants = []
        if self.process.poll() is None:
            try:
                parent = psutil.Process(self.process.pid)
                if parent.create_time() != self.create_time or parent.cmdline() != self.command:
                    raise RuntimeError("The dashboard process identity changed; no process was signalled")
                descendants = parent.children(recursive=True)
            except psutil.NoSuchProcess:
                descendants = []
        for child in descendants:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                continue
        stop_owned_server(self.process)
        _, alive = psutil.wait_procs(descendants, timeout=3)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                continue
        psutil.wait_procs(alive, timeout=3)
        self.stopped = True


def launch_dashboard(*, root: Path | None = None, manifest: Path | None = None,
                     port: int = 8501, startup_timeout: float = 90,
                     remote_repository: str | None = None, remote_ref: str = "main") -> ModuleDashboard:
    """Verify the complete kit and render its installed app before starting HTTP."""
    from cochem.core.context import assert_writable_path

    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Dashboard port must be an integer between 1 and 65535")
    if isinstance(startup_timeout, bool) or not math.isfinite(startup_timeout) or startup_timeout <= 0:
        raise ValueError("Dashboard startup timeout must be finite and positive")
    selected_root = (root or manager.default_root()).expanduser().resolve()
    spec = manager.load_manifest(manifest or manager.DEFAULT_MANIFEST)["modules"]["topos"]
    if spec.get("adapter") != "topos_handoff":
        raise ValueError("The complete dashboard requires the reviewed mandatory TOPOS kit")
    receipt = manager.verify_installation("topos", spec, selected_root)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))
    import uuid

    output = selected_root.parent / "Dashboards" / f"topos-{uuid.uuid4().hex}"
    assert_writable_path(output)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    environment = dashboard_environment(Path(receipt["runtime_path"]), output,
        remote_repository=remote_repository, remote_ref=remote_ref, base_commit=receipt["source_pins"]["base"])
    python = receipt["python_path"]
    probe_log = output / "render-probe.log"
    with probe_log.open("w", encoding="utf-8") as log:
        probe = subprocess.run([python, "-I", "-B", "-c", _PROBE], cwd=output, env=environment,
                               stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                               timeout=startup_timeout, check=False)
    if probe.returncode:
        raise RuntimeError(f"Installed TOPOS interface failed its rendering check; inspect {probe_log}")
    command = [python, "-I", "-B", "-c", "from topos.ui import ui_main; raise SystemExit(ui_main())",
               "--port", str(port)]
    with (output / "streamlit.log").open("ab") as log:
        process = subprocess.Popen(command, cwd=output, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name != "nt")
    dashboard = None
    try:
        identity = psutil.Process(process.pid)
        dashboard = ModuleDashboard(process, port, output, spec["revision"], command,
                                    identity.create_time(), browser_url(port))
        deadline = time.monotonic() + startup_timeout
        while process.poll() is None and time.monotonic() < deadline:
            if owns_listener(identity, port) and page_ready(port):
                if identity.cmdline() != command:
                    raise RuntimeError("Dashboard did not run the verified installed entry point")
                manager._atomic_json(output / "launch.json", {"schema_version": "cochem.module-dashboard/1",
                    "module_id": "topos", "revision": spec["revision"], "runtime_path": receipt["runtime_path"],
                    "python_path": python, "port": port, "url": dashboard.url, "published": False,
                    "render_probe_passed": True, "scientific_execution_performed": False})
                return dashboard
            time.sleep(.2)
    except BaseException:
        if dashboard is not None:
            dashboard.stop()
        else:
            from scripts.hosted_dashboard import stop_owned_server
            stop_owned_server(process)
        raise
    dashboard.stop()
    raise RuntimeError(f"TOPOS interface startup failed; inspect {output / 'streamlit.log'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="BASE module storage containing the verified complete kit")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--startup-timeout", type=float, default=90)
    parser.add_argument("--remote-repository", help="Student's private project with its TOPOS compute workflow")
    parser.add_argument("--remote-ref", default="main", help="Explicit controller branch or tag")
    args = parser.parse_args(argv)
    try:
        dashboard = launch_dashboard(root=args.root, manifest=args.manifest, port=args.port,
                                     startup_timeout=args.startup_timeout,
                                     remote_repository=args.remote_repository, remote_ref=args.remote_ref)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"TOPOS interface was not started: {error}", file=sys.stderr)
        return 2
    print(f"TOPOS interface ready: {dashboard.url}. Keep Codespaces forwarded port visibility private.", flush=True)
    print(f"Runtime logs: {dashboard.output}. Press Ctrl+C to stop the owned interface and its jobs.", flush=True)
    try:
        return int(dashboard.process.wait())
    except KeyboardInterrupt:
        return 0
    finally:
        dashboard.stop()


if __name__ == "__main__":
    raise SystemExit(main())
