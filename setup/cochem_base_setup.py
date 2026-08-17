#!/usr/bin/env python3
"""
CoChem-BASE Setup Script
This script handles the environment setup and detection logic for CoChem-BASE.
"""

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
repo_root_str = str(REPO_ROOT)
sys.path[:] = [repo_root_str, *(entry for entry in sys.path if entry != repo_root_str)]

import ipywidgets as widgets  # noqa: E402
from IPython.display import HTML, display  # noqa: E402

from cochem_base.config_loader import (  # noqa: E402
    get_artifact_dir,
    resolve_conda_executable,
    resolve_mapped_path,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-BaseSetup")

SILO_SETUP_SCRIPT = REPO_ROOT / "setup" / "cochem_base_silo_setup.py"

try:
    from core_engine.cochem_core_subprocess_broker import (
        register_popen_process,
        safe_subprocess_run,
    )
except ImportError:
    safe_subprocess_run: Any = None  # type: ignore
    register_popen_process: Any = None  # type: ignore


class EnvConfig(BaseModel):
    artifact_dir: str


def _silo_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(REPO_ROOT), existing_pythonpath) if path
    )
    return env


def _map_artifact_dir(value: str) -> Path:
    artifact_dir = resolve_mapped_path(value, Path.home())
    os.environ["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)
    return artifact_dir


def _launch_silo_setup() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, str(SILO_SETUP_SCRIPT)],
        cwd=str(REPO_ROOT),
        env=_silo_subprocess_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1
    )


def _environment_exists(env_dir: Path) -> bool:
    """Validate a prefix independently of Conda's human-readable path formatting."""
    conda_meta_path = env_dir / "conda-meta"
    has_metadata = conda_meta_path.is_dir() and any(conda_meta_path.glob("*.json"))
    try:
        conda_executable = resolve_conda_executable(required=False)
        if conda_executable is not None:
            command = [str(conda_executable), "info", "--envs"]
            if safe_subprocess_run is not None:
                safe_subprocess_run(command, check=True, timeout=30.0)
            else:
                subprocess.run(command, check=True, capture_output=True, text=True, timeout=30.0)
        else:
            logger.warning("Conda executable not found.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.warning(f"Conda registry check failed; validating prefix metadata directly: {exc}")
    if env_dir.exists() and not has_metadata:
        logger.warning(f"Environment directory is missing Conda metadata: {conda_meta_path}")
    return has_metadata


def provision_silo(artifact_path: str, log_callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, Path, bool]:
    """
    Core logic for provisioning the silo. Decoupled from the UI.
    Returns (success, env_dir, was_already_provisioned).
    """
    artifact_dir = _map_artifact_dir(artifact_path)
    cfg_path = REPO_ROOT / ".cochem_env.json"
    cfg = EnvConfig(artifact_dir=str(artifact_dir))
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(cfg.model_dump_json())
    logger.info(f"Saved Artifact registry path to: {cfg_path}")
    logger.info(f"Target Artifact Director: {artifact_dir}\n")

    env_dir = artifact_dir / "Silos" / "cochem_base_silo"
    env_exists = _environment_exists(env_dir)

    if env_exists:
        logger.info(f"Conda environment detected at: {env_dir}")
        logger.info("   Skipping full setup - using existing environment")
        return True, env_dir, True

    logger.info("Handing off to Silo creation agent...\n")

    try:
        proc = _launch_silo_setup()
        if register_popen_process is not None:
            register_popen_process(proc)

        import atexit
        def _kill_proc() -> None:
            if proc.poll() is None:
                proc.kill()
        atexit.register(_kill_proc)

        try:
            if proc.stdout:
                for line in iter(proc.stdout.readline, ''):
                    if log_callback:
                        log_callback(line)
            proc.wait(timeout=3600.0)
        finally:
            atexit.unregister(_kill_proc)
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        return proc.returncode == 0, env_dir, False
    except subprocess.TimeoutExpired:
        if log_callback:
            log_callback("Error: Silo setup timed out after 3600 seconds.\n")
        return False, env_dir, False
    except OSError as e:
        if log_callback:
            log_callback(f"OS Error launching script: {e}\n")
        return False, env_dir, False


def _get_success_html(env_dir: Path, already_provisioned: bool) -> str:
    status_msg = "✅ Conda Silo Already Provisioned!" if already_provisioned else "✅ Conda Silo Provisioned!"
    env_msg = f"Using existing environment at: {env_dir}<br><br>" if already_provisioned else ""
    return f"""
        <div style="padding: 10px; background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; color: #155724; margin-top: 15px;">
            <b>{status_msg}</b><br><br>
            {env_msg}
            Please click the secure link below to trigger the VS Code Kernel Selector. <br>
            Select the <b>cochem_base_silo</b> environment, wait 2 seconds for it to attach, and then execute the UI Matrix block below.<br><br>
            <a href="command:notebook.selectKernel" style="font-size: 16px; font-weight: bold; padding: 5px 10px; background-color: #155724; color: white; text-decoration: none; border-radius: 3px;">🔄 Select cochem_base_silo Kernel</a>
        </div>
    """


def setup_cochem_base() -> None:
    """Main setup function for CoChem-BASE environment"""
    logger.info("=======================================================")
    logger.info(" ⚙️ CoChem-BASE: Artifact & Silo Registry Configuration")
    logger.info("=======================================================\n")

    cfg_path = REPO_ROOT / ".cochem_env.json"
    previous_path: Optional[str] = None
    if cfg_path.exists():
        try:
            config = EnvConfig.model_validate_json(cfg_path.read_text(encoding="utf-8"))
            previous_path = config.artifact_dir
        except (ValidationError, OSError) as e:
            logger.debug(f"Failed to read previous artifact configuration from .cochem_env.json: {e}")

    def _handle_provision(path_val: str, path_input_widget: widgets.Text, btn_to_disable1: widgets.Button, btn_to_disable2: Optional[widgets.Button], output_widget: widgets.Output) -> None:
        with output_widget:
            output_widget.clear_output()

            log_output = widgets.Textarea(value='', disabled=True, layout=widgets.Layout(height='250px', width='100%'))

            def thread_target() -> None:
                def log_cb(msg: str) -> None:
                    log_output.value += msg

                artifact_dir = resolve_mapped_path(path_val, Path.home())
                env_dir = artifact_dir / "Silos" / "cochem_base_silo"
                env_exists = _environment_exists(env_dir)

                if not env_exists:
                    display(log_output)

                success, env_dir_res, already = provision_silo(path_val, log_cb)

                path_input_widget.value = str(_map_artifact_dir(path_val))

                if success:
                    output_widget.append_display_data(HTML(_get_success_html(env_dir_res, already)))
                else:
                    log_output.value += "\n❌ Silo build failed.\n"

                btn_to_disable1.disabled = False
                if btn_to_disable2:
                    btn_to_disable2.disabled = False
                if "New" in btn_to_disable1.description:
                    btn_to_disable1.description = "Set New Path & Build Silo"
                else:
                    btn_to_disable1.description = "Set Path & Build Silo"

            threading.Thread(target=thread_target, daemon=True).start()

    if previous_path:
        path_input = widgets.Text(
            value=previous_path,
            placeholder="Enter absolute path",
            description="Storage Path:",
            layout=widgets.Layout(width="80%")
        )
        keep_btn = widgets.Button(description="Keep Previous Path", button_style="info", layout=widgets.Layout(width="150px"))
        set_btn = widgets.Button(description="Set New Path & Build Silo", button_style="success", layout=widgets.Layout(width="200px"))

        output = widgets.Output()

        def on_keep_click(b: Any) -> None:
            path_input.value = previous_path
            set_btn.disabled = True
            keep_btn.disabled = True
            set_btn.description = "Checking Silo..."
            _handle_provision(previous_path, path_input, set_btn, keep_btn, output)

        def on_set_click(b: Any) -> None:
            set_btn.disabled = True
            keep_btn.disabled = True
            set_btn.description = "Checking Silo..."
            _handle_provision(path_input.value, path_input, set_btn, keep_btn, output)

        keep_btn.on_click(on_keep_click)
        set_btn.on_click(on_set_click)

        display(widgets.VBox([
            widgets.HBox([path_input, keep_btn, set_btn]),
            output
        ]))

        logger.info(f"Previous configuration detected: {previous_path}")
        logger.info("   Click 'Keep Previous Path' to use the existing setup")
        logger.info("   Or modify the path and click 'Set New Path & Build Silo'")
    else:
        path_input = widgets.Text(
            value=str(get_artifact_dir()),
            placeholder="Enter absolute path",
            description="Storage Path:",
            layout=widgets.Layout(width="80%")
        )
        set_btn = widgets.Button(description="Set Path & Build Silo", button_style="success", layout=widgets.Layout(width="200px"))
        output = widgets.Output()

        def on_click(b: Any) -> None:
            set_btn.disabled = True
            set_btn.description = "Building Silo..."
            _handle_provision(path_input.value, path_input, set_btn, None, output)

        set_btn.on_click(on_click)
        display(widgets.VBox([widgets.HBox([path_input, set_btn]), output]))


if __name__ == "__main__":
    setup_cochem_base()
