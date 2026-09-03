"""
CoChem Base: Configuration Loader & Dynamic Path Resolver
Provides universal config loading, root directory discovery, and executable resolution.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple, Union

logger = logging.getLogger("cochem_base.config_loader")

def get_cochem_root() -> Path:
    """Discovers and returns the absolute path to the CoChem repository root."""
    if "COCHEM_ROOT" in os.environ and os.environ["COCHEM_ROOT"]:
        p = Path(os.environ["COCHEM_ROOT"]).resolve()
        if p.exists():
            return p
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "cochem_system_config.json").exists() or (parent / "CoChem-BASE").exists():
            return parent
        if parent.name == "GitHub-Repo":
            return parent
    return Path("d:/__CoChem/GitHub-Repo").resolve()

def get_base_root() -> Path:
    """Returns the root directory of the CoChem-BASE module."""
    root = get_cochem_root()
    base_dir = root / "CoChem-BASE"
    return base_dir if base_dir.exists() else root

def get_repo_root() -> Path:
    """Alias for get_cochem_root()."""
    return get_cochem_root()

def get_modules_dir() -> Path:
    """Returns modules directory."""
    return get_cochem_root()

def get_runtime_dir() -> Path:
    """Returns runtime directory."""
    return get_scratch_dir()

def get_artifact_dir(override: Optional[Union[str, Path]] = None) -> Path:
    """Returns the path to the artifacts directory."""
    if override:
        p = Path(override).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    if "COCHEM_ARTIFACTS" in os.environ:
        p = Path(os.environ["COCHEM_ARTIFACTS"]).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    if "COCHEM_ARTIFACT_DIR" in os.environ:
        p = Path(os.environ["COCHEM_ARTIFACT_DIR"]).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    root = get_cochem_root()
    art_dir = root / "artifacts"
    if not art_dir.exists():
        art_dir = root.parent / "CoChem_Artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    return art_dir

def get_scratch_dir() -> Path:
    """Returns the fast local scratch directory."""
    art = get_artifact_dir()
    scratch = art / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    return scratch

def get_cochem_scratch() -> Path:
    """Alias for get_scratch_dir()."""
    return get_scratch_dir()

def get_ramdisk_dir() -> Optional[Path]:
    """Returns ramdisk path if configured."""
    return None

def get_state_file_path() -> Path:
    """Returns the global swarm state file path."""
    return get_cochem_root() / "swarm_state.json"

def resolve_config_path(target: Optional[Union[str, Path]] = None) -> Path:
    """Resolves cochem_system_config.json location."""
    if target:
        p = Path(target).resolve()
        if p.exists():
            return p
    if "COCHEM_CONFIG" in os.environ:
        p = Path(os.environ["COCHEM_CONFIG"]).resolve()
        if p.exists():
            return p
    root = get_cochem_root()
    candidates = [
        root / "cochem_system_config.json",
        root / "CoChem-BASE" / "cochem_system_config.json",
        root / "CoChem-SEED" / "cochem_system_config.json",
        Path.cwd() / "cochem_system_config.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

def load_system_config_dict(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Loads system configuration dictionary from disk."""
    resolved = resolve_config_path(config_path)
    if resolved.exists():
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                data = json.load(f)
                return dict(data) if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning("Failed loading config from %s: %s", resolved, e)
    return {}

def load_system_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Alias for load_system_config_dict."""
    return load_system_config_dict(config_path)

def get_default_cochem_config() -> Dict[str, Any]:
    """Returns default system config dict."""
    return load_system_config_dict()

def resolve_mapped_path(path_str: str, base_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves mapped or relative paths to absolute."""
    p = Path(path_str)
    if p.is_absolute():
        return p
    base = Path(base_dir).resolve() if base_dir else get_cochem_root()
    return (base / p).resolve()

def resolve_executable(
    binary_name: Optional[str] = None,
    env_var: Optional[str] = None,
    candidates: Sequence[str] = (),
) -> str:
    """Resolves full executable path for quantum chemistry or MPI packages."""
    if env_var and env_var in os.environ:
        val = os.environ[env_var]
        if val and shutil.which(val):
            return shutil.which(val) or val
        if val and Path(val).exists():
            return val

    if binary_name:
        found = shutil.which(binary_name)
        if found:
            return found
        if Path(binary_name).exists():
            return binary_name

    for cand in candidates:
        found = shutil.which(cand)
        if found:
            return found
        if Path(cand).exists():
            return cand

    # Default common Windows paths
    if binary_name in ("orca", "orca.exe") or "orca" in candidates:
        for p in [r"C:\ORCA_6.1.1\orca.exe", r"C:\ORCA\orca.exe"]:
            if Path(p).exists():
                return p

    if binary_name in ("mpirun", "mpiexec") or "mpirun" in candidates or "mpiexec" in candidates:
        for p in [r"C:\Program Files\Microsoft MPI\Bin\mpiexec.exe", r"C:\Program Files\Microsoft MPI\Bin\mpirun.exe"]:
            if Path(p).exists():
                return p

    return binary_name or (candidates[0] if candidates else "")

def resolve_conda_executable(binary_name: str) -> str:
    """Resolves conda binary."""
    return resolve_executable(binary_name)

def resolve_wsl_executable(binary_name: str) -> str:
    """Resolves WSL executable."""
    return resolve_executable(binary_name)

def get_mps_directories() -> Tuple[Path, Path]:
    """Returns pipe and log directories for NVIDIA MPS."""
    pipe_dir = Path(tempfile.gettempdir()) / "nvidia-mps"
    log_dir = Path(tempfile.gettempdir()) / "nvidia-log"
    pipe_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    return pipe_dir, log_dir

def get_telemetry_socket_path() -> Path:
    """Returns telemetry IPC socket path."""
    return get_scratch_dir() / "cochem_telemetry.sock"

def get_telemetry_transport() -> str:
    """Returns telemetry transport mode."""
    return "udp" if platform.system() == "Windows" else "ipc"

def get_telemetry_udp_address() -> Tuple[str, int]:
    """Returns telemetry UDP host and port."""
    return ("127.0.0.1", 45454)

def prepend_executable_directory(exe_path: str) -> None:
    """Prepends directory containing executable to PATH."""
    p = Path(exe_path).resolve()
    if p.exists() and p.is_file():
        d = str(p.parent)
        cur = os.environ.get("PATH", "")
        if d not in cur:
            os.environ["PATH"] = f"{d}{os.pathsep}{cur}"

def update_config(key: str, value: Any, config_path: Optional[Union[str, Path]] = None) -> None:
    """Updates key in cochem_system_config.json."""
    cfg = load_system_config_dict(config_path)
    cfg[key] = value
    target = resolve_config_path(config_path)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
