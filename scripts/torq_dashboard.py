"""Open modern TORQ's student interface in its verified separate environment.

BASE verifies the installation before importing module code. HTTP readiness
establishes interface availability; calculation routes need their own approval
and deployed worker. Authentication is private to this owned server instance.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from scripts import manage_modules as manager
from scripts.module_dashboard import ModuleDashboard, browser_url, owns_listener

_PROBE = """import hashlib, json, os, pathlib, sys
import cochem_torq.ui, cochem_torq.student_app
from importlib.resources import files
prefix = pathlib.Path(sys.prefix).resolve()
for module in (cochem_torq.ui, cochem_torq.student_app):
    if not pathlib.Path(module.__file__).resolve().is_relative_to(prefix):
        raise RuntimeError('TORQ interface must belong to its installed environment')
notebook = cochem_torq.ui.prepare_notebook(sys.argv[1])
original = files('UI').joinpath('Start_TORQ.ipynb').read_bytes()
if notebook.read_bytes() != original:
    raise RuntimeError('New TORQ workspace did not preserve the packaged notebook')
app = cochem_torq.student_app.launch_student_app(results_directory=sys.argv[2])
if app.student_session.request is not None:
    raise RuntimeError('Rendering TORQ cannot prepare a scientific request')
if 'application/vnd.jupyter.widget-view+json' not in app._repr_mimebundle_():
    raise RuntimeError('Installed TORQ did not render its actual student widget')
app.close()
print(json.dumps({'notebook': str(notebook),
    'notebook_sha256': hashlib.sha256(original).hexdigest(),
    'interface_module': str(pathlib.Path(cochem_torq.student_app.__file__).resolve()),
    'allow_root': hasattr(os, 'geteuid') and os.geteuid() == 0,
    'scientific_execution_performed': False}))
"""


def interface_environment(
    python: Path,
    output: Path,
    inherited: dict[str, str] | None = None,
    *,
    remote_repository: str | None = None,
    remote_ref: str = "main",
    source_revision: str | None = None,
) -> dict[str, str]:
    """Keep account authentication; remove engine, source and loader overrides."""
    values = dict(os.environ if inherited is None else inherited)
    prefixes = (
        "GIT_",
        "LD_",
        "DYLD_",
        "PYTHON",
        "COCHEM_",
        "COCH_",
        "TOPOS_",
        "TORQ_",
        "ORCA",
        "CFOUR",
        "XTB",
        "CREST",
        "JUPYTER",
        "IPYTHON",
    )
    environment = {
        key: value
        for key, value in values.items()
        if key != "VIRTUAL_ENV"
        and not key.startswith(prefixes)
        and not any(
            word in key.upper()
            for word in (
                "TOKEN",
                "SECRET",
                "PASSWORD",
                "PASSWD",
                "CREDENTIAL",
                "AUTHORIZATION",
            )
        )
        and not key.upper().endswith("_KEY")
    }
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        if key in values:
            environment[key] = values[key]
    mode = values.get("COCHEM_PRIVATE_GH_AUTH", "auto")
    if mode not in {"auto", "stored-cli", "environment"}:
        raise ValueError("COCHEM_PRIVATE_GH_AUTH must be auto, stored-cli, or environment.")
    environment["COCHEM_PRIVATE_GH_AUTH"] = mode
    if remote_repository is not None:
        if not manager.REPOSITORY_PATTERN.fullmatch(remote_repository):
            raise ValueError("TORQ's calculation target must be OWNER/REPOSITORY.")
        if not remote_ref or any(ord(character) < 33 for character in remote_ref):
            raise ValueError("TORQ's calculation ref must be explicit and contain no whitespace.")
        environment["COCHEM_TORQ_GITHUB_REPOSITORY"] = remote_repository
        environment["COCHEM_TORQ_CALCULATION_REF"] = remote_ref
    if source_revision is not None:
        if not isinstance(source_revision, str) or len(source_revision) != 40:
            raise ValueError("TORQ source revision must be an immutable Git SHA.")
        if any(character not in "0123456789abcdef" for character in source_revision):
            raise ValueError("TORQ source revision must be an immutable Git SHA.")
        environment["COCHEM_SOURCE_COMMIT"] = source_revision
    environment.update(
        PATH=os.pathsep.join((str(python.parent), os.defpath)),
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        COCHEM_ARTIFACT_DIR=str(output),
        COCHEM_CALCULATION_ENVIRONMENT="github-actions",
    )
    for variable, directory in {
        "JUPYTER_CONFIG_DIR": "jupyter-config",
        "JUPYTER_DATA_DIR": "jupyter-data",
        "JUPYTER_RUNTIME_DIR": "jupyter-runtime",
        "IPYTHONDIR": "ipython",
        "XDG_CACHE_HOME": "cache",
        "MPLCONFIGDIR": "matplotlib",
        "TMPDIR": "scratch",
    }.items():
        folder = output / directory
        folder.mkdir(mode=0o700, exist_ok=True)
        environment[variable] = str(folder)
    configuration = Path(environment["JUPYTER_CONFIG_DIR"]) / "jupyter_server_config.py"
    configuration.write_text(
        "c.Application.log_level = 'ERROR'\n"
        "c.ServerApp.log_level = 'ERROR'\n"
        "c.ServerApp.allow_remote_access = True\n",
        encoding="utf-8",
    )
    configuration.chmod(0o600)
    return environment


def _request(port: int, path: str, authorization: str) -> bytes:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/{path}",
        headers={"Authorization": "token " + authorization},
    )
    with opener.open(request, timeout=2) as response:
        if response.status != 200:
            raise ValueError("TORQ's authenticated service did not return HTTP 200.")
        return response.read(2 * 1024 * 1024)


def _interface_ready(port: int, notebook_relative: str, authorization: str) -> bool:
    try:
        status = json.loads(_request(port, "api/status", authorization))
        notebook = json.loads(_request(port, "api/contents/" + notebook_relative, authorization))
        page = _request(port, "lab/tree/" + notebook_relative, authorization)
        return (
            isinstance(status, dict)
            and notebook.get("type") == "notebook"
            and any(
                "launch_student_app" in "".join(cell.get("source", []))
                for cell in notebook["content"]["cells"]
                if cell["cell_type"] == "code"
            )
            and b"jupyter" in page.lower()
        )
    except (OSError, urllib.error.URLError, ValueError, KeyError, TypeError):
        return False


@dataclass
class TorqDashboard(ModuleDashboard):
    """Owned post-exec Jupyter process; credentials never appear in its repr."""

    url: str = field(repr=False)
    connection_file: Path | None = field(default=None, repr=False)
    public_url: str = ""
    topos_producer_python: Path | None = None
    topos_producer: dict | None = None

    def stop(self) -> None:
        super().stop()
        if self.connection_file is not None:
            self.connection_file.unlink(missing_ok=True)
        self.url = self.public_url


def _start_interface(
    python: Path,
    output: Path,
    *,
    port: int,
    startup_timeout: float,
    revision: str | None = None,
    inherited: dict[str, str] | None = None,
    remote_repository: str | None = None,
    remote_ref: str = "main",
    topos_producer: dict | None = None,
) -> TorqDashboard:
    """Start actual installed code; public callers first verify its BASE receipt."""
    from cochem.core.context import assert_writable_path

    assert_writable_path(output)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    environment = interface_environment(
        python,
        output,
        inherited,
        remote_repository=remote_repository,
        remote_ref=remote_ref,
        source_revision=revision,
    )
    probe = subprocess.run(
        [
            str(python),
            "-I",
            "-B",
            "-c",
            _PROBE,
            str(output / "workspace"),
            str(output / "downloads"),
        ],
        cwd=output,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=startup_timeout,
        check=False,
    )
    if probe.returncode:
        raise RuntimeError("Installed TORQ interface failed its isolated rendering probe.")
    observation = json.loads(probe.stdout)
    notebook = Path(observation["notebook"])
    notebook_relative = notebook.relative_to(output / "workspace").as_posix()
    authorization = secrets.token_urlsafe(32)
    environment["JUPYTER_TOKEN"] = authorization
    command = [
        str(python),
        "-I",
        "-B",
        "-m",
        "cochem_torq.ui",
        "--workspace",
        str(output / "workspace"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    expected_command = [
        str(python),
        "-m",
        "jupyterlab",
        "--no-browser",
        "--ServerApp.ip=127.0.0.1",
        f"--ServerApp.port={port}",
        "--ServerApp.port_retries=0",
        f"--ServerApp.root_dir={output / 'workspace'}",
        f"--ServerApp.default_url=/lab/tree/{notebook_relative}",
    ]
    if observation["allow_root"]:
        expected_command.append("--allow-root")
    log_path = output / "jupyter.log"
    with log_path.open("xb") as log:
        log_path.chmod(0o600)
        process = subprocess.Popen(
            command,
            cwd=output,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )
    dashboard = None
    try:
        identity = psutil.Process(process.pid)
        creation = identity.create_time()
        deadline = time.monotonic() + startup_timeout
        while process.poll() is None and time.monotonic() < deadline:
            if owns_listener(identity, port) and _interface_ready(
                port, notebook_relative, authorization
            ):
                if identity.cmdline() != expected_command or identity.create_time() != creation:
                    raise RuntimeError(
                        "TORQ's post-exec process differs from its installed Jupyter entry point."
                    )
                base_url = browser_url(port)
                login_url = (
                    base_url
                    + "/lab/tree/"
                    + notebook_relative
                    + "?"
                    + urllib.parse.urlencode({"token": authorization})
                )
                connection = output / "connection.json"
                with connection.open("x", encoding="utf-8") as stream:
                    os.chmod(connection, 0o600)
                    json.dump({"url": login_url, "private": True}, stream)
                dashboard = TorqDashboard(
                    process,
                    port,
                    output,
                    revision or "unbound-installed-interface",
                    expected_command,
                    creation,
                    login_url,
                    connection_file=connection,
                    public_url=base_url,
                    topos_producer_python=Path(topos_producer["python_path"]) if topos_producer is not None else None,
                    topos_producer=topos_producer,
                )
                manager._atomic_json(
                    output / "launch.json",
                    {
                        "schema_version": "cochem.torq-dashboard/1",
                        "module_id": "torq",
                        "revision": revision,
                        "python_path": str(python),
                        "port": port,
                        "url": base_url,
                        "pid": process.pid,
                        "create_time": creation,
                        "command": expected_command,
                        "published": False,
                        "render_probe_passed": True,
                        "authenticated_notebook_ready": True,
                        "scientific_execution_performed": False,
                        "hosted_calculation_deployment_verified": False,
                        "topos_producer": topos_producer,
                    },
                )
                return dashboard
            time.sleep(0.2)
    except BaseException:
        if dashboard is not None:
            dashboard.stop()
        else:
            from scripts.hosted_dashboard import stop_owned_server

            stop_owned_server(process)
        raise
    from scripts.hosted_dashboard import stop_owned_server

    stop_owned_server(process)
    raise RuntimeError("TORQ's authenticated interface did not become ready.")


def managed_topos_producer(root: Path, manifest: Path | None = None) -> dict | None:
    """Expose the existing mandatory producer only after genuine verification.

    An absent producer permits standalone TORQ inputs and explicit out-of-band
    producers. A present broken receipt must never appear as a verified producer.
    No environment variable or guessed sibling executable supplies authority.
    """
    root = root.expanduser().absolute()
    receipt_file = root / "topos/installation.json"
    if receipt_file.is_symlink():
        raise ValueError("The managed TOPOS installation receipt cannot be redirected")
    if not receipt_file.exists():
        return None
    spec = manager.load_manifest(manifest or manager.DEFAULT_MANIFEST)["modules"]["topos"]
    verified = manager.verify_installation("topos", spec, root)
    return {"status": "verified", "python_path": verified["python_path"],
            "source_pins": verified["source_pins"],
            "installation_receipt_sha256": manager._digest_json(verified),
            "scope": "Verified installed producer for explicit TOPOS handoff integrity checks; no calculation or publication acceptance"}


def launch_dashboard(
    *,
    root: Path | None = None,
    manifest: Path | None = None,
    port: int = 8888,
    startup_timeout: float = 60,
    remote_repository: str | None = None,
    remote_ref: str = "main",
) -> TorqDashboard:
    """Verify the isolated modern module before rendering or opening any port."""
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("TORQ dashboard port must be an integer from 1024 through 65535.")
    if (
        isinstance(startup_timeout, bool)
        or not math.isfinite(startup_timeout)
        or not 0 < startup_timeout <= 60
    ):
        raise ValueError("TORQ dashboard startup timeout must be positive and at most 60 seconds.")
    selected_root = (root or manager.default_root()).expanduser().resolve()
    spec = manager.load_manifest(manifest or manager.DEFAULT_MANIFEST)["modules"]["torq"]
    receipt = manager.verify_installation("torq", spec, selected_root)
    producer = managed_topos_producer(selected_root, manifest)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))
    output = selected_root.parent / "Dashboards" / f"torq-{uuid.uuid4().hex}"
    return _start_interface(
        Path(receipt["python_path"]),
        output,
        port=port,
        startup_timeout=startup_timeout,
        revision=spec["revision"],
        remote_repository=remote_repository,
        remote_ref=remote_ref,
        topos_producer=producer,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Open the verified separate TORQ student interface."
    )
    parser.add_argument("--root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--remote-repository")
    parser.add_argument("--remote-ref", default="main")
    arguments = parser.parse_args(argv)
    dashboard = launch_dashboard(
        root=arguments.root,
        manifest=arguments.manifest,
        port=arguments.port,
        remote_repository=arguments.remote_repository,
        remote_ref=arguments.remote_ref,
    )
    print(f"TORQ interface ready. Open its private connection file: {dashboard.connection_file}")
    if dashboard.topos_producer_python is not None:
        print(f"Verified managed TOPOS producer Python: {dashboard.topos_producer_python}")
        print("Paste that path into TORQ's TOPOS Python field for a reviewed TOPOS ensemble.")
    try:
        while dashboard.process.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
