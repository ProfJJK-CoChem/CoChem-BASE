"""# zero-stub anti-spoofing engine
CoChem-GEOM Dynamic Path Resolution & Cross-Platform Path Manager (paths.py)
-------------------------------------------------------------------------------
Provides centralized, dynamic, cross-platform path resolution eliminating all
hardcoded filesystem paths and drive letters across CoChem-GEOM modules.

Features:
1. Dynamic root resolution via COCHEM_ROOT, cwd, parent discovery, and standard fallbacks.
2. Ephemeral scratch and persistent artifact directory managers with automatic creation.
3. Centralized cochem_system_config.json loader and cached singleton accessor.
4. Engine executable and HPC walltime budget resolvers.
5. Strict Path normalization and cross-platform path resolution.

Complies with Method Matrix v4, CoChem Anti-Spoofing Protocol v2, and WBS Task 3.3.4.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    from cochem_geom.engine.schemas import SystemConfigSchema

logger = logging.getLogger("cochem_geom.engine.paths")


# ---------------------------------------------------------------------------
# Dynamic Path Resolution Functions
# ---------------------------------------------------------------------------

def get_cochem_root() -> Path:
    """
    Resolve the CoChem root directory dynamically without hardcoded drive letters.

    Resolution Order:
    1. Environment variable `COCHEM_ROOT`
    2. Current working directory if containing `cochem_system_config.json` or `CoChem-BASE` or `CoChem-GEOM`
    3. Parent directory search starting from `Path.cwd()` and `Path(__file__)`
    4. Fallback: `Path.home() / ".cochem"`
    """
    env_root = os.environ.get("COCHEM_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        return p

    # Search upwards from cwd
    cwd = Path.cwd().resolve()
    for candidate in [cwd, cwd.parent, cwd.parent.parent, cwd.parent.parent.parent]:
        if (candidate / "cochem_system_config.json").exists() or (candidate / "CoChem-BASE").exists() or (candidate / "CoChem-GEOM").exists():
            return candidate

    # Search upwards from this file
    module_dir = Path(__file__).resolve().parent
    for candidate in [module_dir, module_dir.parent, module_dir.parent.parent, module_dir.parent.parent.parent, module_dir.parent.parent.parent.parent]:
        if (candidate / "cochem_system_config.json").exists() or (candidate / "CoChem-BASE").exists() or (candidate / "CoChem-GEOM").exists():
            return candidate

    fallback = Path.home() / ".cochem"
    return fallback


def get_cochem_scratch() -> Path:
    """
    Resolve the ephemeral scratch directory for computational chemistry binaries.
    Guarantees directory creation and returns an absolute Path.

    Resolution Order:
    1. Environment variable `COCHEM_SCRATCH`
    2. `<cochem_root>/scratch` if root exists
    3. System temp directory / `cochem_scratch`
    """
    env_scratch = os.environ.get("COCHEM_SCRATCH")
    if env_scratch:
        p = Path(env_scratch).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    root = get_cochem_root()
    if root.exists():
        scratch_in_root = root / "scratch"
        scratch_in_root.mkdir(parents=True, exist_ok=True)
        return scratch_in_root

    temp_root = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
    p = Path(temp_root).resolve() / "cochem_scratch"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cochem_artifacts() -> Path:
    """
    Resolve the persistent artifacts directory for outputs, datasets, and logs.
    Guarantees directory creation and returns an absolute Path.

    Resolution Order:
    1. Environment variables `COCHEM_ARTIFACTS`, `COCHEM_ARTIFACT_DIR`, or `ARTIFACTS_DIR`
    2. `<cochem_root>/artifacts` if root exists
    3. `Path.home() / "CoChem_Artifacts"` or `Path.home() / ".artifacts" / "cochem"`
    """
    env_art = (
        os.environ.get("COCHEM_ARTIFACTS")
        or os.environ.get("COCHEM_ARTIFACT_DIR")
        or os.environ.get("ARTIFACTS_DIR")
    )
    if env_art:
        p = Path(env_art).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    root = get_cochem_root()
    if root.exists():
        art_dir = root / "artifacts"
        art_dir.mkdir(parents=True, exist_ok=True)
        return art_dir

    if (Path.home() / "CoChem_Artifacts").exists():
        art_dir = Path.home() / "CoChem_Artifacts"
        art_dir.mkdir(parents=True, exist_ok=True)
        return art_dir

    p = Path.home() / ".artifacts" / "cochem"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cochem_trash() -> Path:
    """
    Resolve the safe trash directory for recycled artifacts (No-Kill Python mandate).
    Guarantees directory creation and returns an absolute Path.
    """
    root = get_cochem_root()
    trash_dir = root / ".trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    return trash_dir


def get_workspace_dir(workspace_name: str = "GEOM_Workspace", create: bool = True) -> Path:
    """
    Resolve a named workspace directory dynamically within the artifacts directory
    or via `COCHEM_WORKSPACE` override.
    """
    env_ws = os.environ.get("COCHEM_WORKSPACE")
    if env_ws:
        p = Path(env_ws).resolve()
        if create:
            p.mkdir(parents=True, exist_ok=True)
        return p

    artifacts_dir = get_cochem_artifacts()
    p = artifacts_dir / workspace_name
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_cochem_path(
    relative_or_absolute: Union[str, Path],
    base_dir: Optional[Path] = None,
) -> Path:
    """
    Normalize and resolve a path cleanly across Windows and POSIX systems.
    Absolute paths are resolved directly; relative paths are resolved against
    base_dir (or get_cochem_root()).
    """
    p = Path(relative_or_absolute)
    if p.is_absolute():
        return p.resolve()
    base = base_dir or get_cochem_root()
    return (base / p).resolve()


def find_system_config_path(
    explicit_path: Optional[Union[str, Path]] = None,
) -> Optional[Path]:
    """
    Discover the active cochem_system_config.json configuration file path.

    Search Order:
    1. Explicit path parameter if provided and exists
    2. Environment variable `COCHEM_CONFIG`
    3. `<cochem_root>/cochem_system_config.json`
    4. `<cochem_root>/Registry/cochem_system_config.json`
    5. `<cochem_root>/artifacts/Registry/cochem_system_config.json`
    6. `<artifacts_dir>/Registry/cochem_system_config.json`
    7. `Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json"`
    8. `Path.home() / ".cochem" / "cochem_system_config.json"`
    """
    if explicit_path is not None:
        cp = Path(explicit_path).resolve()
        if cp.exists() and cp.is_file():
            return cp
        return None

    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg:
        cp = Path(env_cfg).resolve()
        if cp.exists() and cp.is_file():
            return cp
        return None

    root = get_cochem_root()
    candidate_paths: List[Path] = [
        root / "cochem_system_config.json",
        root / "Registry" / "cochem_system_config.json",
        root / "artifacts" / "Registry" / "cochem_system_config.json",
        get_cochem_artifacts() / "Registry" / "cochem_system_config.json",
        Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json",
        Path.home() / ".cochem" / "cochem_system_config.json",
    ]

    for cp in candidate_paths:
        if cp.exists() and cp.is_file():
            return cp.resolve()

    return None


get_system_config_path = find_system_config_path


# ---------------------------------------------------------------------------
# Configuration Loader
# ---------------------------------------------------------------------------

_GLOBAL_SYSTEM_CONFIG: Optional[SystemConfigSchema] = None


def load_system_config(
    config_path: Optional[Union[str, Path]] = None,
) -> SystemConfigSchema:
    """
    Load and parse cochem_system_config.json into a SystemConfigSchema instance.
    Falls back gracefully to dynamic defaults if config file is not found.
    """
    from cochem_geom.engine.schemas import SystemConfigSchema

    discovered_path = find_system_config_path(config_path)
    artifacts_dir_str = str(get_cochem_artifacts())
    workspace_dir_str = str(get_cochem_root())
    scratch_dir_str = str(get_cochem_scratch())

    if discovered_path and discovered_path.exists():
        try:
            raw_text = discovered_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)

            hw = data.get("hardware", {})
            engines = data.get("engines", {})
            hpc = data.get("hpc", {})

            cpu_cores = hw.get("cpu_cores", hw.get("physical_cpu_cores", os.cpu_count() or 4))
            ram_mb = hw.get("ram_mb", 32768)
            calc_maxcore = max(512, ram_mb // max(1, cpu_cores))

            env_nprocs = os.environ.get("COCHEM_NPROCS")
            final_nprocs = int(env_nprocs) if env_nprocs else max(1, min(cpu_cores, 16))

            env_maxcore = os.environ.get("COCHEM_MAXCORE")
            final_maxcore = int(env_maxcore) if env_maxcore else calc_maxcore

            orca_path = engines.get("orca", {}).get("path", "orca") if isinstance(engines.get("orca"), dict) else "orca"
            cfour_path = engines.get("cfour", {}).get("path", "cfour") if isinstance(engines.get("cfour"), dict) else "cfour"
            xtb_path = engines.get("xtb", {}).get("path", "xtb") if isinstance(engines.get("xtb"), dict) else "xtb"
            pyscf_path = engines.get("pyscf", {}).get("path", "pyscf") if isinstance(engines.get("pyscf"), dict) else "pyscf"
            crest_path = engines.get("crest", {}).get("path", "crest") if isinstance(engines.get("crest"), dict) else "crest"
            goat_path = engines.get("goat", {}).get("path", "goat") if isinstance(engines.get("goat"), dict) else "goat"

            schema = SystemConfigSchema(
                schema_version=data.get("schema_version", "4.0.0"),
                nprocs=final_nprocs,
                maxcore=final_maxcore,
                artifacts_dir=artifacts_dir_str,
                workspace_dir=workspace_dir_str,
                scratch_dir=scratch_dir_str,
                orca_executable=orca_path,
                cfour_executable=cfour_path,
                xtb_executable=xtb_path,
                pyscf_executable=pyscf_path,
                crest_executable=crest_path,
                goat_executable=goat_path,
                hardware=hw,
                engines=engines,
                hpc=hpc,
            )
            logger.info(f"Successfully loaded CoChem system configuration from {discovered_path}")
            return schema
        except Exception as e:
            logger.warning(f"Failed parsing system config at {discovered_path}: {e}. Initializing dynamic fallback.")

    default_nprocs = int(os.environ.get("COCHEM_NPROCS", max(1, (os.cpu_count() or 4) - 2)))
    default_maxcore = int(os.environ.get("COCHEM_MAXCORE", 4000))
    return SystemConfigSchema(
        nprocs=default_nprocs,
        maxcore=default_maxcore,
        artifacts_dir=artifacts_dir_str,
        workspace_dir=workspace_dir_str,
        scratch_dir=scratch_dir_str,
        orca_executable=os.environ.get("ORCA_CMD", "orca"),
        cfour_executable=os.environ.get("CFOUR_CMD", "cfour"),
        xtb_executable=os.environ.get("XTB_CMD", "xtb"),
    )


def get_system_config(
    config_path: Optional[Union[str, Path]] = None,
    reload: bool = False,
) -> SystemConfigSchema:
    """
    Retrieve cached global system configuration instance.
    """
    global _GLOBAL_SYSTEM_CONFIG
    if _GLOBAL_SYSTEM_CONFIG is None or reload:
        _GLOBAL_SYSTEM_CONFIG = load_system_config(config_path)
    return _GLOBAL_SYSTEM_CONFIG


def get_engine_executable(
    engine_name: str,
    config: Optional[SystemConfigSchema] = None,
) -> str:
    """
    Retrieve the configured executable binary path or command for a given quantum engine.
    """
    cfg = config or get_system_config()
    if hasattr(cfg, "get_engine_path"):
        ep = cfg.get_engine_path(engine_name)
        if ep:
            return str(ep)
    return engine_name.lower()


def get_hpc_walltime_budget(
    tier: str,
    config: Optional[SystemConfigSchema] = None,
) -> str:
    """
    Retrieve Method Matrix walltime budget string for an HPC tier (e.g. 'T1-10s' -> '00:00:10').
    """
    cfg = config or get_system_config()
    if hasattr(cfg, "get_walltime_budget"):
        return str(cfg.get_walltime_budget(tier))
    return "01:00:00"


# ---------------------------------------------------------------------------
# Sterile Quarantine Topology & Strict Permissions
# ---------------------------------------------------------------------------

def apply_strict_permissions(
    path: Union[str, Path],
    mode: int = 0o700,
    strict_nt: bool = True,
) -> bool:
    """
    Apply strict POSIX or Windows NT permissions to a target directory or file.

    Parameters:
        path: Filesystem path to directory or file.
        mode: POSIX permission bitmask (default: 0o700 for owner rwx only).
        strict_nt: If True on Windows NT, strip inherited ACLs and grant exclusive Full Control
                   to the active user account via icacls.

    Returns:
        bool: True if permission hardening succeeded (or completed with graceful fallback),
              False if the target path does not exist or chmod failed.
    """
    target = Path(path).resolve()
    if not target.exists():
        return False

    success = True
    try:
        os.chmod(target, mode)
    except Exception as e:
        logger.warning(f"Failed to apply chmod {oct(mode)} to {target}: {e}")
        success = False

    if sys.platform == "win32" and strict_nt:
        username = os.environ.get("USERNAME")
        if not username:
            try:
                import getpass
                username = getpass.getuser()
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                pass

        if username:
            try:
                perm_flag = "(OI)(CI)F" if target.is_dir() else "F"
                cmd = [
                    "icacls",
                    str(target),
                    "/inheritance:r",
                    "/grant:r",
                    f"{username}:{perm_flag}",
                ]
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if res.returncode != 0:
                    logger.debug(
                        f"icacls on {target} returned code {res.returncode}: {res.stderr.strip()}"
                    )
            except Exception as e:
                logger.debug(f"NT ACL isolation on {target} skipped or failed gracefully: {e}")

    return success


def get_quarantine_topology(
    base_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Path]:
    """
    Compute sterile directory quarantine topology mapping.
    Maps standard subfolder keys {'hdf5', 'logs', 'inputs', 'outputs', 'checkpoints'}
    under the target base directory (defaulting to get_cochem_artifacts()).

    Parameters:
        base_dir: Base directory path, or None to use get_cochem_artifacts().

    Returns:
        Dict[str, Path]: Mapping of topology keys to absolute Path objects.
    """
    base = Path(base_dir).resolve() if base_dir is not None else get_cochem_artifacts()
    return {
        "hdf5": base / "hdf5",
        "logs": base / "logs",
        "inputs": base / "inputs",
        "outputs": base / "outputs",
        "checkpoints": base / "checkpoints",
    }


def generate_quarantine_topology(
    base_dir: Optional[Union[str, Path]] = None,
    mode: int = 0o700,
    strict_nt: bool = True,
) -> Dict[str, Path]:
    """
    Create sterile directory quarantine topology:
    CoChem_Artifacts/{hdf5,logs,inputs,outputs,checkpoints}
    with strict POSIX/NT permissions applied to base and all quarantine subdirectories.

    Parameters:
        base_dir: Base directory path, or None to use get_cochem_artifacts().
        mode: POSIX permission mode (default 0o700).
        strict_nt: Whether to enforce Windows NT ACL user isolation.

    Returns:
        Dict[str, Path]: Mapping of quarantine category names to created Path instances.
    """
    base = Path(base_dir).resolve() if base_dir is not None else get_cochem_artifacts()
    base.mkdir(parents=True, exist_ok=True)
    apply_strict_permissions(base, mode=mode, strict_nt=strict_nt)

    topology = get_quarantine_topology(base)
    for path in topology.values():
        path.mkdir(parents=True, exist_ok=True)
        apply_strict_permissions(path, mode=mode, strict_nt=strict_nt)

    return topology

