#!/usr/bin/env python3
"""
CoChem-BASE Central Dynamic Configuration & Path Loader.
Provides authoritative, Pydantic-validated access to cochem_system_config.json
and dynamic workspace paths following the 4-tier resolution hierarchy.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import socket
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, MutableMapping, Optional, Sequence, Union

if TYPE_CHECKING:
    from core_engine.cochem_core_registry_schema import CoChemConfig

logger = logging.getLogger(__name__)

BASE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = BASE_ROOT.parent


def resolve_mapped_path(path_value: Union[str, Path], base_dir: Optional[Path] = None) -> Path:
    """Expand and anchor a user or environment supplied path deterministically."""
    expanded = Path(os.path.expandvars(str(path_value))).expanduser()
    if not expanded.is_absolute():
        expanded = (base_dir or BASE_ROOT) / expanded
    return expanded.resolve()


def get_runtime_dir() -> Path:
    """Return a writable host-native directory for sockets and transient state."""
    mapped_runtime = os.environ.get("COCHEM_RUNTIME_DIR")
    runtime_dir = (
        resolve_mapped_path(mapped_runtime, Path(tempfile.gettempdir()))
        if mapped_runtime
        else (Path(tempfile.gettempdir()) / "cochem").resolve()
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def get_telemetry_socket_path() -> Path:
    """Resolve the local telemetry socket path without assuming a POSIX /tmp tree."""
    mapped_socket = os.environ.get("COCHEM_TELEMETRY_SOCKET")
    if mapped_socket:
        return resolve_mapped_path(mapped_socket, get_runtime_dir())
    return get_runtime_dir() / "cochem_telemetry.sock"


def get_telemetry_transport() -> str:
    """Select Unix datagrams where supported and UDP on Windows by default."""
    configured = os.environ.get("COCHEM_TELEMETRY_TRANSPORT", "").strip().lower()
    if configured:
        if configured not in {"unix", "udp"}:
            raise ValueError("COCHEM_TELEMETRY_TRANSPORT must be 'unix' or 'udp'.")
        if configured == "unix" and not hasattr(socket, "AF_UNIX"):
            raise RuntimeError("Unix sockets were requested but are unavailable on this host.")
        return configured
    return "udp" if platform.system() == "Windows" or not hasattr(socket, "AF_UNIX") else "unix"


def get_telemetry_udp_address() -> tuple[str, int]:
    """Return the configured loopback UDP endpoint used as the portable fallback."""
    host = os.environ.get("COCHEM_TELEMETRY_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.environ.get("COCHEM_TELEMETRY_PORT", "8765"))
    except ValueError as exc:
        raise ValueError("COCHEM_TELEMETRY_PORT must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("COCHEM_TELEMETRY_PORT must be between 1 and 65535.")
    return host, port


def get_state_file_path(filename: str = "cochem_state.h5") -> Path:
    """Resolve persistent HDF5 state under the artifact registry by default."""
    mapped_state = os.environ.get("COCHEM_STATE_FILE")
    if mapped_state:
        return resolve_mapped_path(mapped_state, get_artifact_dir())
    return get_artifact_dir() / filename


def get_mps_directories() -> tuple[Path, Path]:
    """Resolve CUDA MPS pipe and log directories using host-native runtime storage."""
    runtime_dir = get_runtime_dir()
    pipe_value = os.environ.get("CUDA_MPS_PIPE_DIRECTORY")
    log_value = os.environ.get("CUDA_MPS_LOG_DIRECTORY")
    pipe_dir = resolve_mapped_path(pipe_value, runtime_dir) if pipe_value else runtime_dir / "nvidia-mps"
    log_dir = resolve_mapped_path(log_value, runtime_dir) if log_value else runtime_dir / "nvidia-log"
    return pipe_dir, log_dir


def get_ramdisk_dir() -> Optional[Path]:
    """Return an explicitly mapped or host-native RAM disk when one is available."""
    mapped_ramdisk = os.environ.get("COCHEM_RAMDISK_DIR")
    if mapped_ramdisk:
        return resolve_mapped_path(mapped_ramdisk, get_runtime_dir())
    if platform.system() == "Linux":
        linux_ramdisk = Path(os.sep) / "dev" / "shm"
        if linux_ramdisk.is_dir():
            return linux_ramdisk
    return None


def get_base_root() -> Path:
    """Return the CoChem-BASE checkout containing this module."""
    configured = os.environ.get("COCHEM_BASE_ROOT")
    if configured:
        return resolve_mapped_path(configured)
    return BASE_ROOT


def get_repo_root() -> Path:
    """Return the workspace root containing the CoChem repositories."""
    configured = os.environ.get("COCHEM_WORKSPACE_ROOT") or os.environ.get("COCHEM_ROOT")
    if configured:
        return resolve_mapped_path(configured)
    return WORKSPACE_ROOT


def get_cochem_root() -> Path:
    """Return the repository workspace root or ~/.cochem fallback."""
    configured = os.environ.get("COCHEM_ROOT") or os.environ.get("COCHEM_WORKSPACE_ROOT")
    if configured:
        return resolve_mapped_path(configured)
    try:
        current_file = Path(__file__).resolve()
        base_dir = current_file.parent.parent
        if (base_dir / "cochem_base").is_dir():
            ws = base_dir.parent
            if ws.exists():
                return ws
            return base_dir
    except Exception:
        pass
    return (Path.home() / ".cochem").resolve()


def get_scratch_dir(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """5-Tier scratch directory resolution hierarchy:
    Tier 1: Explicit custom_path parameter
    Tier 2: COCHEM_SCRATCH or COCHEM_SCRATCH_DIR environment variable
    Tier 3: XDG_CACHE_HOME / cochem / scratch
    Tier 4: tempfile.gettempdir() / cochem_scratch
    Tier 5: Path.home() / .cochem / scratch
    """
    if custom_path is not None:
        p = resolve_mapped_path(custom_path)
        p.mkdir(parents=True, exist_ok=True)
        return p
    env_scratch = os.environ.get("COCHEM_SCRATCH") or os.environ.get("COCHEM_SCRATCH_DIR")
    if env_scratch:
        p = resolve_mapped_path(env_scratch)
        p.mkdir(parents=True, exist_ok=True)
        return p
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        p = (resolve_mapped_path(xdg_cache) / "cochem" / "scratch").resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    try:
        tempdir = Path(tempfile.gettempdir())
        p = (tempdir / "cochem_scratch").resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        pass
    p = (Path.home() / ".cochem" / "scratch").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cochem_scratch(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Alias for get_scratch_dir."""
    return get_scratch_dir(custom_path=custom_path)


def resolve_executable(
    value: Optional[str] = None,
    *,
    env_var: Optional[str] = None,
    candidates: Sequence[str] = (),
) -> str:
    """Resolve an executable from an explicit mapping, environment variable, or PATH."""
    mapped_value = (value or (os.environ.get(env_var) if env_var else None) or "").strip()
    if mapped_value:
        discovered = shutil.which(mapped_value)
        if discovered:
            return str(Path(discovered).resolve())

        mapped_path = Path(os.path.expandvars(mapped_value)).expanduser()
        if mapped_path.is_dir():
            executable_names = list(candidates)
            if platform.system() == "Windows":
                executable_names.extend(f"{name}.exe" for name in candidates if not name.endswith(".exe"))
            for executable_name in executable_names:
                executable_path = mapped_path / executable_name
                if executable_path.is_file():
                    return str(executable_path.resolve())

        if mapped_path.is_absolute() or mapped_path.parent != Path("."):
            return str(resolve_mapped_path(mapped_path))
        return mapped_value

    for candidate in candidates:
        discovered = shutil.which(candidate)
        if discovered:
            return str(Path(discovered).resolve())
    return candidates[0] if candidates else ""


def resolve_conda_executable(required: bool = True) -> str:
    """Resolve Conda, Mamba, or Micromamba from configuration or PATH."""
    configured = os.environ.get("COCHEM_CONDA_EXE") or os.environ.get("CONDA_EXE")
    candidates = ("conda", "mamba", "micromamba")
    if configured:
        resolved = resolve_executable(configured, candidates=candidates)
        if Path(resolved).is_file() or shutil.which(resolved):
            return resolved
        if required:
            raise FileNotFoundError(f"Configured Conda executable was not found: {configured}")

    resolved = resolve_executable(candidates=candidates)
    if Path(resolved).is_file() or shutil.which(resolved):
        return resolved
    if required:
        raise FileNotFoundError(
            "Conda-compatible executable not found. Set COCHEM_CONDA_EXE or add conda, mamba, or micromamba to PATH."
        )
    return "conda"


def resolve_wsl_executable(required: bool = False) -> str:
    """Resolve WSL from an explicit mapping or PATH on Windows hosts."""
    resolved = resolve_executable(
        os.environ.get("COCHEM_WSL_EXE"),
        candidates=("wsl.exe", "wsl"),
    )
    if Path(resolved).is_file() or shutil.which(resolved):
        return resolved
    if required:
        raise FileNotFoundError("WSL was not found. Set COCHEM_WSL_EXE or add wsl to PATH.")
    return ""


def prepend_executable_directory(
    env: MutableMapping[str, str],
    executable: Optional[Union[str, Path]],
) -> MutableMapping[str, str]:
    """Prepend an explicitly mapped executable directory to a child PATH."""
    if not executable:
        return env
    executable_path = Path(str(executable)).expanduser()
    if not executable_path.is_file():
        return env
    executable_dir = str(executable_path.resolve().parent)
    current_path = env.get("PATH", "")
    path_entries = [entry for entry in current_path.split(os.pathsep) if entry]
    if executable_dir not in path_entries:
        env["PATH"] = os.pathsep.join((executable_dir, *path_entries))
    return env


def get_default_cochem_config() -> CoChemConfig:
    """Returns the fallback default CoChemConfig model instance."""
    from core_engine.cochem_core_registry_schema import CoChemConfig

    return CoChemConfig(
        hardware={  # type: ignore
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 16.0,
            "avx512_support": False,
            "gpu_profile": "None",
            "vram_gb": 0.0,
            "subnormal_precision_trap": False,
            "os_target": f"{platform.system().lower()}_{platform.machine().lower()}"
        },
        engines={
            "orca": {"status": "missing", "path": None, "version": None, "hash": None},
            "mpirun": {"status": "missing", "path": None, "version": None, "hash": None},
            "xtb": {"status": "missing", "path": None, "version": None, "hash": None}
        },
        silos={"torq_silo_active": False, "gpu_silo_active": False}  # type: ignore
    )


def resolve_config_path(custom_path: Optional[Path] = None) -> Path:
    """
    Resolves cochem_system_config.json path via 4-tier resolution hierarchy:
    Tier 1: Explicit Parameter (Function/CLI Argument)
    Tier 2: Environment Variables (COCHEM_CONFIG, COCHEM_ARTIFACT_DIR)
    Tier 3: Central System Config (cochem_system_config.json in repo root or CoChem-BASE)
    Tier 4: Dynamic Workspace Discovery (Anchored relative to repo root)
    """
    if custom_path is not None:
        return resolve_mapped_path(custom_path)

    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg:
        mapped_config = resolve_mapped_path(env_cfg)
        if mapped_config.exists():
            return mapped_config

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        art_cfg = resolve_mapped_path(env_art, Path.home()) / "cochem_system_config.json"
        if art_cfg.exists():
            return art_cfg

    repo_cfg = get_repo_root() / "cochem_system_config.json"
    if repo_cfg.exists():
        return repo_cfg

    base_cfg = get_repo_root() / "CoChem-BASE" / "cochem_system_config.json"
    if base_cfg.exists():
        return base_cfg

    # Fallback to creating/defaulting inside repo root
    return repo_cfg


def load_system_config(config_path: Optional[Path] = None) -> CoChemConfig:
    """Loads and validates cochem_system_config.json into a CoChemConfig Pydantic model."""
    from core_engine.cochem_core_registry_schema import CoChemConfig

    target_path = resolve_config_path(config_path)
    if not target_path.exists():
        raise FileNotFoundError(f"CRITICAL: Configuration file not found at {target_path}. Computed defaults designed to keep the process alive are forbidden.")

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw_data = json.loads(f.read())
    except (json.JSONDecodeError, ValueError, OSError) as e:
        raise ValueError(f"CRITICAL: Failed to read or parse JSON config at {target_path}: {e}. Computed defaults designed to keep the process alive are forbidden.") from e

    # Computed defaults for os_target removed per Exception Deflection Test mandate.

    try:
        return CoChemConfig.model_validate(raw_data)
    except Exception as e:
        raise ValueError(f"CRITICAL: Config schema validation error for {target_path}: {e}. Computed defaults designed to keep the process alive are forbidden.") from e


def load_system_config_dict(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads validated system configuration as a dictionary."""
    cfg = load_system_config(config_path)
    return cfg.model_dump()


def get_artifact_dir() -> Path:
    """Dynamically resolves artifact workspace directory."""
    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return resolve_mapped_path(env_art, Path.home())

    repo_artifacts = get_repo_root() / ".agent_artifacts"
    if repo_artifacts.exists():
        return repo_artifacts

    home_artifacts = Path.home() / "CoChem_Artifacts"
    return home_artifacts


def get_modules_dir() -> Path:
    """Resolve the directory containing CoChem module repositories."""
    env_modules = os.environ.get("COCHEM_MODULE_DIR")
    if env_modules:
        return resolve_mapped_path(env_modules, get_artifact_dir())

    required_modules = ("CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ")
    if all((WORKSPACE_ROOT / module_name).is_dir() for module_name in required_modules):
        return WORKSPACE_ROOT

    artifact_dir = get_artifact_dir()
    for candidate in (artifact_dir / "Registry" / "Modules", artifact_dir / "modules"):
        if candidate.is_dir():
            return candidate.resolve()
    return artifact_dir / "Registry" / "Modules"
def update_config(config_obj: CoChemConfig, config_path: Optional[Path] = None) -> None:
    """Writes a CoChemConfig model back to cochem_system_config.json."""
    target_path = resolve_config_path(config_path)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(config_obj.model_dump_json(indent=2))
