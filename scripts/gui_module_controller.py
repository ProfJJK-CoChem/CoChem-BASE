"""Bridge a checkout notebook to the actual isolated installed BASE controller.

The notebook may display current source UI code. Mandatory execution authority
belongs to the noneditable installed distribution, selected with isolated Python.
Reports and diagnostics stay in new external directories, without source imports
or an ownership-check exception.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil

MAX_REPORT = 16 * 1024 * 1024
CLI_MODULES = {"scripts.manage_modules", "scripts.run_module_handoff", "scripts.gui_module_controller"}


class InstalledControlError(RuntimeError):
    def __init__(self, message: str, *, task_id: str | None = None):
        super().__init__(message)
        self.task_id = task_id


def _external_new(path: Path) -> Path:
    from scripts.private_engine_assets import _private_output
    selected = _private_output(path)
    selected.mkdir(parents=True, mode=0o700, exist_ok=False)
    return selected


def _report(path: Path):
    from scripts.private_engine_assets import _json
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_REPORT:
        raise ValueError("Installed controller returned no bounded regular JSON report")
    return _json(path.read_bytes())


def _cap_diagnostics(path: Path) -> bool:
    if path.stat().st_size <= MAX_REPORT:
        return False
    with path.open('r+b') as stream:
        stream.truncate(MAX_REPORT)
    return True


def _launch(module: str, arguments: list[str], output: Path) -> tuple[subprocess.Popen, list[str]]:
    if module not in CLI_MODULES or any(not isinstance(value, str) or '\x00' in value for value in arguments):
        raise ValueError("Select a supported installed BASE control entry point")
    command = [sys.executable, "-I", "-B", "-m", module, *arguments]
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "PYTHONSTARTUP", "LD_PRELOAD"}}
    with (output / "report.json").open("xb") as report, (output / "diagnostics.log").open("xb") as diagnostics:
        os.chmod(output / 'report.json', 0o600)
        os.chmod(output / 'diagnostics.log', 0o600)
        process = subprocess.Popen(command, cwd=output, env=environment, stdin=subprocess.DEVNULL,
            stdout=report, stderr=diagnostics, start_new_session=os.name != "nt")
    return process, command


def run_installed_cli(module: str, arguments: list[str], output: Path, *, timeout: float,
                      cancellation_event=None):
    """Execute the genuine packaged CLI; retain a failed report and stderr log."""
    from scripts.hosted_dashboard import stop_owned_server
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("The installed controller needs a finite positive deadline")
    output = _external_new(output)
    process, _ = _launch(module, arguments, output)
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if cancellation_event is not None and cancellation_event.is_set():
                raise RuntimeError("Installed module operation cancelled; diagnostics retained")
            if time.monotonic() >= deadline:
                raise TimeoutError("Installed module controller deadline exhausted")
            if (output / "report.json").stat().st_size > MAX_REPORT or (output / "diagnostics.log").stat().st_size > MAX_REPORT:
                raise ValueError("Installed controller exceeded its bounded report allocation")
            time.sleep(.1)
        if _cap_diagnostics(output / 'diagnostics.log'):
            raise ValueError("Installed controller diagnostics exceeded the allocation and were truncated")
        if process.returncode:
            task_id = None
            try:
                failure = _report(output / 'report.json')
                if isinstance(failure, dict) and failure.get('status') == 'failed':
                    from cochem_base.interfaces.private_actions import TASK_PATTERN
                    candidate = failure.get('task_id')
                    if isinstance(candidate, str) and TASK_PATTERN.fullmatch(candidate):
                        task_id = candidate
            except (OSError, ValueError):
                pass
            raise InstalledControlError(f"Installed BASE controller exited {process.returncode}; inspect {output / 'diagnostics.log'}",
                                        task_id=task_id)
        return _report(output / "report.json")
    except BaseException:
        if process.poll() is None:
            children = _descendants(psutil.Process(process.pid))
            stop_owned_server(process)
            _stop_descendants(children)
        _cap_diagnostics(output / 'diagnostics.log')
        raise


@dataclass
class InstalledDashboard:
    process: subprocess.Popen
    command: list[str]
    create_time: float
    output: Path
    revision: str
    url: str = field(repr=False)
    topos_producer_python: Path | None = None
    service: dict | None = None
    stopped: bool = False

    def stop(self) -> None:
        if self.stopped:
            return
        if self.process.poll() is None:
            actual = psutil.Process(self.process.pid)
            if actual.cmdline() != self.command or actual.create_time() != self.create_time:
                raise RuntimeError("Refusing to stop a controller whose process ownership differs")
            children = _descendants(actual)
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                from scripts.hosted_dashboard import stop_owned_server
                stop_owned_server(self.process)
            _stop_descendants(children)
        _stop_service(self.service)
        self.stopped = True


def _descendants(actual: psutil.Process) -> list[tuple[int, float]]:
    observed = []
    for child in actual.children(recursive=True):
        try:
            observed.append((child.pid, child.create_time()))
        except psutil.NoSuchProcess:
            pass
    return observed


def _stop_descendants(children: list[tuple[int, float]]) -> None:
    for pid, created in reversed(children):
        try:
            actual = psutil.Process(pid)
            if actual.create_time() == created and actual.is_running():
                actual.kill()
                _, alive = psutil.wait_procs([actual], timeout=1)
                if alive and actual.status() != psutil.STATUS_ZOMBIE:
                    raise RuntimeError("An owned controller descendant did not terminate")
        except psutil.NoSuchProcess:
            pass


def _stop_service(service: dict | None) -> None:
    """Remove an owned separately-sessioned server after controller failure."""
    if service is None:
        return
    try:
        actual = psutil.Process(service['pid'])
        if actual.status() == psutil.STATUS_ZOMBIE:
            return
        if actual.create_time() != service['create_time'] or actual.cmdline() != service['command']:
            raise RuntimeError("Refusing to stop a server whose process ownership differs")
        children = _descendants(actual)
        actual.terminate()
        try:
            actual.wait(timeout=5)
        except psutil.TimeoutExpired:
            actual.kill()
            actual.wait(timeout=5)
        _stop_descendants(children)
    except psutil.NoSuchProcess:
        pass


def start_installed_dashboard(module_id: str, root: Path, output: Path, *, port: int,
                              remote_repository: str | None, remote_ref: str) -> InstalledDashboard:
    if module_id not in {"topos", "torq"}:
        raise ValueError("Select TOPOS or TORQ's installed interface")
    output = _external_new(output)
    ready = output / "ready.json"
    arguments = ["serve", "--module", module_id, "--root", str(root.expanduser().absolute()), "--port", str(port),
                 "--ready", str(ready), "--remote-ref", remote_ref]
    if remote_repository:
        arguments += ["--remote-repository", remote_repository]
    process, command = _launch("scripts.gui_module_controller", arguments, output)
    creation = psutil.Process(process.pid).create_time()
    try:
        deadline = time.monotonic() + 180
        while process.poll() is None and time.monotonic() < deadline:
            if ready.exists():
                value = _report(ready)
                if value.get("controller_pid") != process.pid or value.get("module_id") != module_id:
                    raise ValueError("Installed interface readiness differs from its actual controller")
                return InstalledDashboard(process, command, creation, Path(value["output"]), value["revision"],
                    value["url"], Path(value["topos_producer_python"]) if value["topos_producer_python"] else None,
                    value['service'])
            time.sleep(.1)
        raise RuntimeError(f"Installed {module_id} controller did not start; inspect {output / 'diagnostics.log'}")
    except BaseException:
        from scripts.hosted_dashboard import stop_owned_server
        children = _descendants(psutil.Process(process.pid)) if process.poll() is None else []
        stop_owned_server(process)
        _stop_descendants(children)
        if ready.exists():
            value = _report(ready)
            if value.get('controller_pid') == process.pid:
                _stop_service(value.get('service'))
        raise


def _serve(arguments) -> int:
    from threading import Event

    from scripts import manage_modules as manager
    from scripts.private_engine_assets import _private_output

    arguments.ready = _private_output(arguments.ready)
    if arguments.ready.exists():
        raise ValueError('Use a new private interface readiness file')
    if arguments.module == "topos":
        from scripts.module_dashboard import launch_dashboard
    else:
        from scripts.torq_dashboard import launch_dashboard
    stopped = Event()
    for selected in (signal.SIGTERM, signal.SIGINT):
        signal.signal(selected, lambda *_: stopped.set())
    dashboard = launch_dashboard(root=arguments.root, port=arguments.port,
        remote_repository=arguments.remote_repository, remote_ref=arguments.remote_ref)
    try:
        manager._atomic_json(arguments.ready, {"controller_pid": os.getpid(), "module_id": arguments.module,
            "output": str(dashboard.output), "revision": dashboard.revision, "url": dashboard.url,
            "topos_producer_python": str(getattr(dashboard, "topos_producer_python", "") or ""),
            "service": {'pid': dashboard.process.pid, 'command': dashboard.command, 'create_time': dashboard.create_time}})
        arguments.ready.chmod(0o600)
        while not stopped.wait(.2) and dashboard.process.poll() is None:
            pass
        return 0
    finally:
        dashboard.stop()
        arguments.ready.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    status = modes.add_parser('status')
    status.add_argument('--root', type=Path)
    serve = modes.add_parser('serve')
    serve.add_argument('--root', type=Path, required=True)
    serve.add_argument('--module', choices=('topos', 'torq'), required=True)
    serve.add_argument('--port', type=int, required=True)
    serve.add_argument('--ready', type=Path, required=True)
    serve.add_argument('--remote-repository')
    serve.add_argument('--remote-ref', default='main')
    private = modes.add_parser('private-actions')
    private.add_argument('--control', type=Path, required=True)
    arguments = parser.parse_args(argv)
    if not Path(__file__).absolute().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError("GUI module controls require the actual installed BASE distribution")
    if arguments.mode == "serve":
        return _serve(arguments)
    if arguments.mode == "status":
        from cochem_base.interfaces.module_execution import installed_module_status
        result = installed_module_status(root=arguments.root)
    else:
        from cochem_base.interfaces.private_topos_actions import PrivateToposActionsController
        from scripts import manage_modules as manager
        from scripts.private_engine_assets import _private_output

        arguments.control = _private_output(arguments.control)
        control = _report(arguments.control)
        if not isinstance(control, dict):
            raise ValueError('Private TOPOS controls must be a JSON object')
        operation = control.get('operation')
        fields = {'operation', 'repository', 'runtime'}
        if operation == 'submit':
            fields |= {'request_file', 'kit', 'root', 'descriptors', 'ref', 'receiver_timeout'}
        elif operation == 'select':
            fields |= {'task', 'run_id'}
        elif operation in {'status', 'cancel', 'download', 'cleanup', 'repair'}:
            fields.add('task')
        else:
            raise ValueError('Select a supported private TOPOS lifecycle operation')
        if set(control) != fields:
            raise ValueError('Private TOPOS controls must match exactly the selected operation')
        controller = PrivateToposActionsController(control["repository"], Path(control["runtime"]))
        if operation == "submit":
            source = _private_output(Path(control['request_file']))
            if not source.is_file() or not 0 < source.stat().st_size <= 256 * 1024:
                raise ValueError('Select the actual bounded frozen private TOPOS request')
            try:
                result = controller.stage_and_dispatch_topos(source.read_bytes(),
                    Path(control["kit"]), Path(control["root"]),
                    {engine: (Path(item[0]), item[1]) for engine, item in control["descriptors"].items()},
                    ref=control["ref"], receiver_timeout=control["receiver_timeout"])
            except Exception:
                import traceback
                failure = {'status': 'failed', 'error_code': 'private-topos-staging-failed',
                           'task_id': getattr(controller, 'last_task_id', None),
                           'scientific_completion_established': False}
                if getattr(controller, "last_task_id", None):
                    interrupted = arguments.control.with_suffix('.interrupted.json')
                    manager._atomic_json(interrupted, failure)
                    interrupted.chmod(0o600)
                print(json.dumps(failure, allow_nan=False))
                traceback.print_exc()
                return 1
        elif operation == "select":
            result = controller.select_run(control["task"], int(control["run_id"]))
        elif operation in {"status", "cancel", "download", "cleanup", "repair"}:
            result = getattr(controller, operation)(control["task"])
        else:
            raise ValueError("Select a supported private TOPOS lifecycle operation")
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
