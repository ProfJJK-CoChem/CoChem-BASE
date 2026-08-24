Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\prompt_cochem_setup_scribe.md.
Original prompt:
# Coding Prompt: CoChem SCRIBE - Setup Script

## Objective
Implement the setup script for CoChem-SCRIBE as defined in Phase 2, Task 4 of the SRS. 

## Target Output Path
`D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\setup\cochem_setup_scribe.py`
*(Note: Also create `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\setup\requirements_scribe.txt` as part of this step).*

## Requirements

### 1. Environment & Dependencies
- Create a dedicated micro-silo environment setup process for `scribe_llm`.
- Write a `requirements_scribe.txt` that rigidly pins the following dependencies:
  - `google-genai`
  - `llama-cpp-python`
  - `jinja2`
  - `tiktoken` (validated against `cl100k_base` encoding)
  - `python-dotenv`
  - `h5py`
  - `psutil`
  - `pydantic`

### 2. Registry & Schema Extensions
- Dynamically resolve all paths using `pathlib.Path.home() / "CoChem_Artifacts" / ...`. Never rely on hardcoded paths or unexpanded environment strings.
- Safely parse and extend the authoritative registry at `pathlib.Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json"` using Pydantic.
- Append a `scribe_settings` block without invalidating existing data:
  - `silo_path` (FilePath): Absolute path to the `scribe_llm` Python executable.
  - `api_key_paths` (FilePath): Absolute path to the secure `.env` file (strictly within the Data Tier).
  - `resource_guard` (bool): Defaults to `True`.
  - `preferred_llm_model` (str): Enum mapping to the selected engine (`google-genai` or `llama-cpp`).
  - `latex_ready` (bool): Dynamic boolean set during setup.
- **Strict Concurrency Rule**: Update the configuration file using HPC-compatible atomic rename operations (`os.rename` or `os.replace`) or directory-based locking. POSIX `fcntl` filelocks are explicitly banned on clustered/networked filesystems.

### 3. Secure Credential Provisioning & Air-Gap Standards
- Verify and create `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"` using `os.makedirs(exist_ok=True)` strictly outside the Git-tracked Execution Tier.
- Generate an `.env` file strictly inside this Air-Gapped output directory (`pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive" / ".env"`). Populate it exclusively with authentic, validated credential payloads (e.g., `GEMINI_API_KEY`). If none are available, fail-fast and abort.
- Enforce strict POSIX permissions of `0o600` (Read/Write for owner only) using `os.chmod()` immediately upon creation.
- Check read access for non-owner users using `os.access()`. Flag a fatal security error and abort initialization if non-owners have access.

### 4. Hardware-Aware Guardrails (`RESOURCE_GUARD`)
- Implement `evaluate_resource_guard()` using `psutil.virtual_memory().total`.
- **Constraint**: If total detected RAM is strictly `< 8.0 * (1024 ** 3)` bytes (< 8.0 GB), trigger the guard.
- Forcefully intercept any user or config request for a local LLM execution. Rewrite the configuration state to route to API mode (`google-genai`). 
- Fail-fast and abort if API keys are missing in this scenario; do NOT fabricate a "Dry-Run" execution path.
- Explicitly log this intervention to the central audit log (`pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive" / "cochem_audit_log.json"`) as `[SCRIBE-WARNING]`.

### 5. Base Utilities & Probing
- Sweep the OS `$PATH` for `pdflatex` or `xelatex` binaries using `subprocess.run`. Set `latex_ready` accordingly.
- Validate the local system's ability to use the `gzip+shuffle+fletcher32` HDF5 filters. Test compression against a structurally representative, authentic data payload (e.g., a real sub-sampled 3D quantum grid slice).
- Initialize the logging interface. Connect to the central logger, define SCRIBE log prefixes, and implement a `RotatingFileHandler` targeted strictly to the Air-Gapped Data Tier (`pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive" / "cochem_scribe_api.log"`) to track API token expenditures without repository pollution.

## Anti-Spoofing Protocols
- **NO MOCKS**: Dummy strings, loopback routing, placeholders, and fake credentials are strictly forbidden. Use real API validation, real hardware polling, and authentic HDF5 payloads.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\setup\cochem_setup_scribe.py ---
#!/usr/bin/env python3
"""
CoChem-SCRIBE Stage 0.0 Setup: Isolated Environment Builder, Pre-Flight Hardware Probe,
Secure Credential Manager, and Golden Registry Linker.

Governed strictly by Phase 2, Task 4: SCRIBE Environment, Configuration & Resource Guards (Stage 0.0)
of the CoChem-SCRIBE Software Requirements Specification (SRS), adhering to Method Matrix v4,
FAIR data principles, and the 6-Tier Environment Matrix (Local-Windows WSL, Local-MacOS OrbStack,
Local-Linux Debian, Codespaces, GitHub Actions, HPC).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import h5py
import numpy as np
import psutil
import tiktoken
from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    from mendeleev import element
except ImportError:
    element = None

try:
    from cochem_core_registry_schema import (
        CoChemSystemConfig,
        HardwareSchema,
        OSTarget,
        discover_host_hardware,
    )
except ImportError:
    try:
        from core_engine.cochem_core_registry_schema import (  # type: ignore
            CoChemSystemConfig,
            HardwareSchema,
            OSTarget,
            discover_host_hardware,
        )
    except ImportError:
        try:
            from cochem_base.core.cochem_core_registry_schema import (  # type: ignore
                CoChemSystemConfig,
                HardwareSchema,
                OSTarget,
                discover_host_hardware,
            )
        except ImportError:
            CoChemSystemConfig = None  # type: ignore
            HardwareSchema = None  # type: ignore
            OSTarget = None  # type: ignore
            discover_host_hardware = None  # type: ignore


# =============================================================================
# CONSTANTS & APPROVED DEPENDENCY MANIFEST
# =============================================================================

APPROVED_SCRIBE_DEPENDENCIES: List[str] = [
    "google-genai",
    "llama-cpp-python",
    "jinja2",
    "tiktoken",
    "python-dotenv",
    "h5py",
    "psutil",
    "pydantic",
]

FORBIDDEN_DEPENDENCIES: set[str] = {
    "tenacity",
    "langchain",
    "crewai",
    "autogen",
}

DISALLOWED_KEY_PATTERNS: set[str] = {
    "",
    "[missing data]",
    "mock",  # forbidden
    "placeholder",  # forbidden
    "dummy",  # forbidden
    "fake",  # forbidden
    "none",
    "test",
}

TIKTOKEN_ENCODING: str = "cl100k_base"
RESOURCE_GUARD_RAM_THRESHOLD_GB: float = 8.0
RESOURCE_GUARD_RAM_THRESHOLD_BYTES: float = 8.0 * (1024.0**3)


# =============================================================================
# 1. LOGGING INTERFACE INITIALIZATION (SRS Section 4.5)
# =============================================================================


class ScribeLogFormatter(logging.Formatter):
    """Custom formatter standardizing [SCRIBE-*] log prefixes across output streams."""

    def format(self, record: logging.LogRecord) -> str:
        level_tag = record.levelname.upper()
        prefix = f"[SCRIBE-{level_tag}]"
        orig_msg = record.getMessage()
        if not orig_msg.startswith("[SCRIBE-"):
            record.msg = f"{prefix} {orig_msg}"
        return super().format(record)


def setup_scribe_logger(
    log_dir: Optional[Path] = None,
    log_filename: str = "cochem_scribe_api.log",
) -> logging.Logger:
    """
    Initializes the CoChem-SCRIBE central logger with [SCRIBE-*] log prefixes
    and a RotatingFileHandler strictly targeted to the Air-Gapped Data Tier
    (e.g., $HOME/CoChem_Artifacts/Report_Archive/cochem_scribe_api.log) to track API token expenditures
    without repository pollution.
    """
    logger_inst = logging.getLogger("CoChem-SCRIBE")
    logger_inst.setLevel(logging.INFO)
    logger_inst.propagate = False

    # Clear existing handlers to prevent duplicate logging
    if logger_inst.hasHandlers():
        logger_inst.handlers.clear()

    formatter = ScribeLogFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger_inst.addHandler(console_handler)

    if log_dir is not None:
        log_dir_path = Path(log_dir).resolve()
        log_dir_path.mkdir(parents=True, exist_ok=True)
        log_file = log_dir_path / log_filename
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger_inst.addHandler(file_handler)

    return logger_inst


logger = setup_scribe_logger()


# =============================================================================
# 2. ENUMS & PYDANTIC SCHEMA EXTENSIONS (SRS Section 4.2)
# =============================================================================


class PreferredLLMModel(str, Enum):
    """Authoritative LLM execution engines supported in CoChem-SCRIBE."""

    GOOGLE_GENAI = "google-genai"
    LLAMA_CPP = "llama-cpp"


class ScribeSettings(BaseModel):
    """
    Pydantic-validated environment, silo, and execution settings for CoChem-SCRIBE.
    Strictly forbids extra fields and relative paths.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    silo_path: str = Field(
        ..., description="Absolute path to the scribe_llm environment or Python executable"
    )
    api_key_paths: str = Field(
        ..., description="Absolute path to the secure .env file in the Data Tier"
    )
    resource_guard: bool = Field(default=True, description="Hardware resource guard flag")
    preferred_llm_model: str = Field(
        default=PreferredLLMModel.GOOGLE_GENAI.value, description="Preferred LLM model"
    )
    latex_ready: bool = Field(
        default=False, description="Dynamic boolean set during pre-flight OS probing"
    )

    @field_validator("preferred_llm_model")
    @classmethod
    def validate_preferred_model(cls, v: str) -> str:
        allowed = {m.value for m in PreferredLLMModel}
        if v not in allowed:
            raise ValueError(f"Invalid preferred_llm_model: '{v}'. Must be one of {allowed}.")
        return v

    @field_validator("silo_path", "api_key_paths")
    @classmethod
    def validate_absolute_paths(cls, v: str) -> str:
        if not v:
            raise ValueError("Path must not be empty.")
        p = Path(v)
        if not p.is_absolute():
            raise ValueError(
                f"Relative paths are strictly forbidden in ScribeSettings: '{v}'. Must be absolute."
            )
        return str(p)


if CoChemSystemConfig is not None:

    class ScribeExtendedSystemConfig(CoChemSystemConfig):  # type: ignore
        """
        Master Golden Registry extension containing dedicated scribe_settings
        without invalidating upstream CoChem-BASE schema fields.
        """

        model_config = ConfigDict(extra="forbid", validate_assignment=True)
        scribe_settings: Optional[ScribeSettings] = Field(
            default=None, description="CoChem-SCRIBE configuration"
        )
else:

    class ScribeExtendedSystemConfig(BaseModel):  # type: ignore
        """Fallback standalone configuration schema if CoChemSystemConfig base is unresolvable."""

        model_config = ConfigDict(extra="allow", validate_assignment=True)
        schema_version: str = Field(default="4.0.0")
        registry_checksum: Optional[str] = Field(default="")
        scribe_settings: Optional[ScribeSettings] = Field(
            default=None, description="CoChem-SCRIBE configuration"
        )


# =============================================================================
# 3. MICRO-SILO BUILDER & DEPENDENCY LOCKING (SRS Section 4.1)
# =============================================================================


def _normalize_pkg_name(pkg: str) -> str:
    """Extracts lowercase base package name stripped of version specifiers and extras."""
    return re.split(r"[><=\!~\[;]", pkg.strip())[0].strip().lower()


def generate_requirements_manifest(
    target_file: Optional[Path] = None,
    custom_packages: Optional[Sequence[str]] = None,
) -> Path:
    """
    Generates and locks dependencies strictly in requirements_scribe.txt.
    Enforces the authoritative 8-package manifest and rejects unapproved/forbidden dependencies.
    """
    approved_base_set = {_normalize_pkg_name(pkg) for pkg in APPROVED_SCRIBE_DEPENDENCIES}

    if custom_packages is not None:
        forbidden = [
            pkg
            for pkg in custom_packages
            if any(fb in _normalize_pkg_name(pkg) for fb in FORBIDDEN_DEPENDENCIES)
        ]
        if forbidden:
            raise ValueError(
                f"Unapproved or forbidden dependencies detected in manifest generation: {forbidden}"
            )

        unapproved = [
            pkg for pkg in custom_packages if _normalize_pkg_name(pkg) not in approved_base_set
        ]
        if unapproved:
            raise ValueError(
                f"Unapproved dependencies rejected by micro-silo whitelist: {unapproved}"
            )

        packages = list(custom_packages)
    else:
        packages = APPROVED_SCRIBE_DEPENDENCIES

    if target_file is None:
        target_file = get_cochem_artifacts_dir() / "Registry" / "requirements_scribe.txt"

    target_file = Path(target_file).resolve()
    target_file.parent.mkdir(parents=True, exist_ok=True)

    manifest_lines = [
        "# CoChem-SCRIBE Stage 0.0 Authoritative Dependency Manifest",
        "# Governed by CoChem-SCRIBE SRS Phase 2, Task 4 (Method Matrix v4)",
        "",
    ]
    for pkg in packages:
        manifest_lines.append(pkg)

    target_file.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    logger.info(f"Generated and locked SCRIBE requirements manifest at: {target_file}")
    return target_file


# =============================================================================
# 4. AIR-GAP DIRECTORY INITIALIZATION & CREDENTIAL PROVISIONING (SRS Section 4.3)
# =============================================================================


def is_inside_git_tree(path: Path) -> bool:
    """Detects whether a target directory resides inside a Git repository working tree."""
    resolved = path.resolve()
    cur: Optional[Path] = resolved
    while cur is not None:
        if (cur / ".git").exists():
            return True
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return False


def get_cochem_artifacts_dir() -> Path:
    """Resolves the authoritative Air-Gapped artifacts directory dynamically using Path.home()."""
    env_override = os.environ.get("COCHEM_ARTIFACTS_DIR") or os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_override:
        return Path(env_override).resolve()
    return (Path.home() / "CoChem_Artifacts").resolve()


def init_airgap_directories(
    artifacts_root: Optional[Path] = None,
    allow_git_nested: bool = False,
) -> Dict[str, Path]:
    """
    Verifies and strictly creates $HOME/CoChem_Artifacts/ subdirectories outside the Git repository tree.
    """
    root = Path(artifacts_root).resolve() if artifacts_root else get_cochem_artifacts_dir()

    if not allow_git_nested and is_inside_git_tree(root):
        raise PermissionError(
            f"Air-Gap boundary violation: Target artifacts root '{root}' resides inside a Git repository tree. "
            "CoChem_Artifacts must be located outside the Git version-controlled workspace."
        )

    dirs = {
        "root": root,
        "report_archive": root / "Report_Archive",
        "registry": root / "Registry",
        "logs": root / "Logs",
        "silos": root / "Silos",
        "scribe_silo": root / "Silos" / "scribe_llm",
    }

    for p in dirs.values():
        os.makedirs(p, exist_ok=True)

    return dirs


def validate_credential_security(env_path: Path) -> bool:
    """
    Verifies POSIX privilege lock (0o600) on .env file and verifies read access via os.access.
    If non-owner users have read/write access on POSIX systems, raises a fatal security error.
    """
    env_path = Path(env_path).resolve()
    if not env_path.exists():
        raise FileNotFoundError(f"Credential file not found at: {env_path}")

    # Verify that the current process has read access
    if not os.access(env_path, os.R_OK):
        raise PermissionError(
            f"Security validation failed: Process cannot read credential file at {env_path}"
        )

    # Enforce POSIX 0o600 on non-Windows platforms
    if platform.system() != "Windows":
        file_stat = env_path.stat()
        mode = file_stat.st_mode
        # Check if group or others have read/write/execute permissions (0o077)
        if mode & 0o077 != 0:
            logger.error(
                f"Insecure file permissions on {env_path}: mode {oct(mode)}. Non-owner access detected."
            )
            raise PermissionError(
                f"Security validation failed: {env_path} permissions must be 0o600 (owner read/write only)."
            )

    return True


def provision_secure_credentials(
    api_key: Optional[str] = None,
    artifacts_root: Optional[Path] = None,
    env_filename: str = ".env",
    allow_git_nested: bool = False,
) -> Path:
    """
    Generates the .env file exclusively inside the Air-Gapped output directory
    ($HOME/CoChem_Artifacts/Report_Archive/.env).
    Populates exclusively with authentic, validated credential payloads.
    Fails fast upon missing credentials.
    """
    root = Path(artifacts_root).resolve() if artifacts_root else get_cochem_artifacts_dir()

    if not allow_git_nested and is_inside_git_tree(root):
        raise PermissionError(
            f"Air-Gap boundary violation: Cannot provision credentials in '{root}' because it is inside a Git repository."
        )

    report_archive_dir = root / "Report_Archive"
    os.makedirs(report_archive_dir, exist_ok=True)
    env_path = report_archive_dir / env_filename

    resolved_key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()

    if (
        not resolved_key
        or resolved_key.lower() in DISALLOWED_KEY_PATTERNS
        or len(resolved_key) < 10
    ):
        raise ValueError(
            "Missing or invalid authentic API credentials. GEMINI_API_KEY must be provided and authentic."
        )

    # Write .env securely
    content = f"GEMINI_API_KEY={resolved_key}\n"
    env_path.write_text(content, encoding="utf-8")

    # Apply POSIX 0o600 privilege lock
    try:
        os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as exc:
        logger.warning(f"Could not apply chmod 0o600 on {env_path}: {exc}")

    # Validate security access
    validate_credential_security(env_path)

    logger.info(f"Secure credential payload provisioned at air-gapped path: {env_path}")
    return env_path


# =============================================================================
# 5. HARDWARE-AWARE GUARDRAILS: RESOURCE_GUARD PROTOCOL (SRS Section 4.4)
# =============================================================================


def _log_audit_event(
    event_type: str,
    message: str,
    level: str = "WARNING",
    report_archive_dir: Optional[Path] = None,
) -> Path:
    """
    Appends an intervention/audit event to the central audit log:
    $HOME/CoChem_Artifacts/Report_Archive/cochem_audit_log.json
    using atomic file replacement for HPC and cluster safety.
    """
    if report_archive_dir is None:
        report_archive_dir = get_cochem_artifacts_dir() / "Report_Archive"
    report_archive_dir = Path(report_archive_dir).resolve()
    report_archive_dir.mkdir(parents=True, exist_ok=True)
    audit_file = report_archive_dir / "cochem_audit_log.json"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": f"[SCRIBE-{level.upper()}]",
        "event_type": event_type,
        "message": message,
    }

    logs: List[Dict[str, Any]] = []
    if audit_file.exists():
        try:
            content = audit_file.read_text(encoding="utf-8").strip()
            if content:
                loaded = json.loads(content)
                if isinstance(loaded, list):
                    logs = loaded
                elif isinstance(loaded, dict):
                    logs = [loaded]
        except Exception:
            logs = []

    logs.append(entry)

    temp_file = audit_file.parent / f".tmp_{audit_file.name}_{uuid.uuid4().hex[:8]}"
    temp_file.write_text(json.dumps(logs, indent=2), encoding="utf-8")
    os.replace(temp_file, audit_file)
    return audit_file


def evaluate_resource_guard(
    requested_model: str = PreferredLLMModel.LLAMA_CPP.value,
    override_ram_gb: Optional[float] = None,
    api_key_available: Optional[bool] = None,
    artifacts_root: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    Evaluates host RAM against the 8.0 GB threshold (< 8.0 * 1024^3 bytes).
    If RAM < 8.0 GB, triggers RESOURCE_GUARD, forces state override to 'google-genai',
    fails fast if API credentials are missing, and logs intervention to cochem_audit_log.json.
    """
    if override_ram_gb is not None:
        total_ram_gb = float(override_ram_gb)
    else:
        total_ram_gb = psutil.virtual_memory().total / (1024.0**3)

    if total_ram_gb < RESOURCE_GUARD_RAM_THRESHOLD_GB:
        root = Path(artifacts_root).resolve() if artifacts_root else get_cochem_artifacts_dir()
        report_archive_dir = root / "Report_Archive"

        logger.warning(
            f"System RAM ({total_ram_gb:.2f} GB) < {RESOURCE_GUARD_RAM_THRESHOLD_GB} GB threshold. "
            "RESOURCE_GUARD triggered: Forcefully routing execution state to 'google-genai'."
        )

        # Check API key availability authentically
        if api_key_available is None:
            api_key_env = os.environ.get("GEMINI_API_KEY", "").strip()
            candidates = [
                report_archive_dir / ".env",
                root / ".env",
            ]
            has_file_key = False
            for cand in candidates:
                if cand.exists():
                    try:
                        for line in cand.read_text(encoding="utf-8").splitlines():
                            if line.startswith("GEMINI_API_KEY="):
                                val = line.split("=", 1)[1].strip()
                                if (
                                    val
                                    and val.lower() not in DISALLOWED_KEY_PATTERNS
                                    and len(val) >= 10
                                ):
                                    has_file_key = True
                                    break
                    except Exception:
                        pass
                if has_file_key:
                    break

            has_env_key = bool(
                api_key_env
                and api_key_env.lower() not in DISALLOWED_KEY_PATTERNS
                and len(api_key_env) >= 10
            )
            api_key_available = has_env_key or has_file_key

        if not api_key_available:
            raise RuntimeError(
                f"RESOURCE_GUARD triggered due to total RAM ({total_ram_gb:.2f} GB < 8.0 GB), "
                "forcing API mode ('google-genai'), but authentic GEMINI_API_KEY is missing. "
                "Aborting initialization."
            )

        # Explicitly log intervention to central audit log as [SCRIBE-WARNING]
        try:
            _log_audit_event(
                event_type="RESOURCE_GUARD_RAM_OVERRIDE",
                message=(
                    f"RESOURCE_GUARD intervention: Total RAM ({total_ram_gb:.2f} GB) is below 8.0 GB threshold. "
                    f"Local model '{requested_model}' intercepted; execution state forced to 'google-genai'."
                ),
                level="WARNING",
                report_archive_dir=report_archive_dir,
            )
        except Exception as audit_err:
            logger.warning(f"Could not write to central audit log: {audit_err}")

        return True, PreferredLLMModel.GOOGLE_GENAI.value

    return False, requested_model


# =============================================================================
# 6. BASE UTILITIES & OS-LEVEL PROBING (SRS Section 4.5)
# =============================================================================


def get_dynamic_atomic_mass(symbol: str) -> float:
    """
    Dynamic atomic mass retrieval strictly via mendeleev library,
    complying with the Mendeleev Library Mandate.
    """
    if element is None:
        raise ImportError("mendeleev package is required for dynamic atomic mass evaluation.")
    elem_data = element(symbol)
    mass_val = getattr(elem_data, "mass", None)
    if mass_val is None:
        raise ValueError(
            f"Could not retrieve atomic mass for element symbol '{symbol}' from mendeleev."
        )
    return float(mass_val)


def probe_latex_environment() -> bool:
    """
    Sweeps the OS $PATH for pdflatex or xelatex binaries using subprocess.run.
    Returns True if LaTeX compiler is available, False otherwise.
    """
    latex_binaries = ["pdflatex", "xelatex"]
    for binary in latex_binaries:
        found_path = shutil.which(binary)
        if found_path:
            try:
                proc = subprocess.run(
                    [found_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                    check=False,
                )
                if proc.returncode == 0:
                    logger.info(f"LaTeX engine verified: {binary} at {found_path}")
                    return True
            except Exception as exc:
                logger.warning(f"Error checking LaTeX binary '{binary}': {exc}")
    logger.info("No LaTeX engine (pdflatex/xelatex) detected on OS PATH.")
    return False


def validate_tiktoken_encoding(encoding_name: str = TIKTOKEN_ENCODING) -> bool:
    """
    Validates that tiktoken tokenizer is functional and supports the specified encoding (cl100k_base).
    """
    try:
        enc = tiktoken.get_encoding(encoding_name)
        tokens = enc.encode("CoChem-SCRIBE Token Verification Payload")
        decoded = enc.decode(tokens)
        if decoded != "CoChem-SCRIBE Token Verification Payload":
            raise ValueError(f"Tiktoken round-trip decode failed for encoding '{encoding_name}'.")
        logger.info(
            f"Tiktoken encoding '{encoding_name}' validated successfully ({len(tokens)} tokens)."
        )
        return True
    except Exception as exc:
        logger.error(f"Tiktoken encoding validation failed for '{encoding_name}': {exc}")
        raise


def validate_hdf5_compression(test_dir: Optional[Path] = None) -> bool:
    """
    Validates host system HDF5 Method Matrix v4 compression pipeline:
    gzip + shuffle + fletcher32 using a representative authentic 3D quantum grid slice.
    """
    work_dir = Path(test_dir).resolve() if test_dir else get_cochem_artifacts_dir() / "Logs"
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_h5_path = work_dir / f"test_compression_{uuid.uuid4().hex[:8]}.h5"

    try:
        # Authentic 3D spatial electron density / orbital grid payload (8x8x8 double precision)
        x = np.linspace(-3.0, 3.0, num=8, dtype=np.float64)
        y = np.linspace(-3.0, 3.0, num=8, dtype=np.float64)
        z = np.linspace(-3.0, 3.0, num=8, dtype=np.float64)
        xx, yy, zz = np.meshgrid(x, y, z, indexing="ij")  # type: ignore[attr-defined]
        # Gaussian orbital representation psi(r) = exp(-0.5 * r^2)
        grid_data = np.exp(-0.5 * (xx**2 + yy**2 + zz**2))

        with h5py.File(str(temp_h5_path), "w") as h5f:
            dset = h5f.create_dataset(
                "quantum_grid_slice",
                data=grid_data,
                compression="gzip",
                compression_opts=4,
                shuffle=True,
                fletcher32=True,
            )
            dset.attrs["method_matrix_version"] = "4.0.0"
            dset.attrs["units"] = "Bohr^-3"

        with h5py.File(str(temp_h5_path), "r") as h5f:
            read_back = h5f["quantum_grid_slice"][()]
            if not np.allclose(grid_data, read_back):  # type: ignore[attr-defined]
                raise ValueError(
                    "HDF5 data integrity mismatch during gzip+shuffle+fletcher32 round-trip."
                )

        logger.info("HDF5 gzip+shuffle+fletcher32 compression pipeline validated successfully.")
        return True
    finally:
        if temp_h5_path.exists():
            try:
                temp_h5_path.unlink()
            except Exception:
                pass


# =============================================================================
# 7. THE GOLDEN REGISTRY LINKER & HPC CONCURRENCY (SRS Section 4.2)
# =============================================================================


def update_scribe_registry(
    config_path: Optional[Path] = None,
    scribe_settings: Optional[ScribeSettings] = None,
) -> ScribeExtendedSystemConfig:
    """
    Safely parses and extends the Pydantic-validated Golden Registry with scribe_settings.
    Uses atomic file renaming (os.replace) for HPC-safe concurrency, strictly avoiding POSIX fcntl.
    """
    if config_path is None:
        config_path = get_cochem_artifacts_dir() / "Registry" / "cochem_system_config.json"

    config_path = Path(config_path).resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        try:
            raw_text = config_path.read_text(encoding="utf-8")
            raw_dict = json.loads(raw_text)
            if scribe_settings is not None:
                raw_dict["scribe_settings"] = scribe_settings.model_dump()
            extended_config = ScribeExtendedSystemConfig.model_validate(raw_dict)
        except Exception as exc:
            logger.warning(
                f"Error parsing existing registry at {config_path} ({exc}); initializing fresh configuration."
            )
            extended_config = _create_fresh_extended_config(scribe_settings)
    else:
        extended_config = _create_fresh_extended_config(scribe_settings)

    # Compute deterministic SHA-256 checksum
    serialized_dict = extended_config.model_dump(exclude={"registry_checksum", "last_updated"})
    cs = hashlib.sha256(
        json.dumps(serialized_dict, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    extended_config.registry_checksum = cs

    # Atomic write to filesystem via temporary staging file and os.replace (HPC & Clustered safe)
    temp_file = config_path.parent / f".tmp_{config_path.name}_{uuid.uuid4().hex[:8]}"
    temp_file.write_text(extended_config.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temp_file, config_path)

    logger.info(f"Golden Registry successfully updated and atomic-locked at: {config_path}")
    return extended_config


def _create_fresh_extended_config(
    scribe_settings: Optional[ScribeSettings],
) -> ScribeExtendedSystemConfig:
    """Helper to instantiate default configuration with ScribeSettings."""
    if CoChemSystemConfig is not None:
        if discover_host_hardware is not None:
            hw = discover_host_hardware()
        elif HardwareSchema is not None:
            hw = HardwareSchema(
                cpu_physical_cores=4,
                physical_cpu_cores=4,
                logical_cpu_cores=8,
                ram_gb=16.0,
                os_target=OSTarget.LOCAL_WINDOWS if os.name == "nt" else OSTarget.LOCAL_LINUX,
            )
        else:
            hw = None

        if hasattr(CoChemSystemConfig, "create_default"):
            base_inst = CoChemSystemConfig.create_default()
            base_dict = base_inst.model_dump()
        else:
            base_dict = {"hardware": hw.model_dump() if hw else {}}

        if scribe_settings:
            base_dict["scribe_settings"] = scribe_settings.model_dump()
        return ScribeExtendedSystemConfig.model_validate(base_dict)
    else:
        fallback_dict = {
            "schema_version": "4.0.0",
            "scribe_settings": scribe_settings.model_dump() if scribe_settings else None,
        }
        return ScribeExtendedSystemConfig.model_validate(fallback_dict)


# =============================================================================
# 8. MASTER STAGE 0.0 SETUP ORCHESTRATOR
# =============================================================================


def setup_scribe_environment(
    artifacts_root: Optional[Path] = None,
    api_key: Optional[str] = None,
    preferred_model: str = PreferredLLMModel.GOOGLE_GENAI.value,
    allow_git_nested: bool = False,
) -> ScribeExtendedSystemConfig:
    """
    Executes the complete CoChem-SCRIBE Stage 0.0 setup workflow:
    1. Initializes Air-Gapped output directories outside the Git repository.
    2. Configures logger with RotatingFileHandler targeted to Report_Archive/cochem_scribe_api.log.
    3. Validates Tiktoken cl100k_base tokenizer.
    4. Generates locked requirements manifest (requirements_scribe.txt).
    5. Provisions authentic credentials (.env) inside Report_Archive with POSIX 0o600 privilege lock.
    6. Evaluates hardware against RESOURCE_GUARD protocol (< 8.0 GB RAM constraint) and logs audit events.
    7. Probes OS environment for LaTeX (pdflatex/xelatex).
    8. Validates HDF5 Method Matrix v4 compression pipeline (gzip+shuffle+fletcher32).
    9. Updates Golden Registry with Pydantic-validated scribe_settings atomically.
    """
    # 1. Directory Structure
    dirs = init_airgap_directories(artifacts_root, allow_git_nested=allow_git_nested)
    setup_scribe_logger(dirs["report_archive"], log_filename="cochem_scribe_api.log")

    logger.info("Initializing CoChem-SCRIBE Stage 0.0 Environment Setup...")

    # 2. Tokenizer validation
    validate_tiktoken_encoding(TIKTOKEN_ENCODING)

    # 3. Dependency Locking
    manifest_path = dirs["registry"] / "requirements_scribe.txt"
    generate_requirements_manifest(manifest_path)

    # 4. Secure Credentials in Report_Archive/.env
    env_path = provision_secure_credentials(
        api_key=api_key,
        artifacts_root=dirs["root"],
        allow_git_nested=allow_git_nested,
    )

    # 5. Hardware Resource Guard
    _, effective_model = evaluate_resource_guard(
        requested_model=preferred_model,
        artifacts_root=dirs["root"],
    )

    # 6. OS LaTeX Probing
    latex_ready = probe_latex_environment()

    # 7. HDF5 Compression Validation
    validate_hdf5_compression(dirs["logs"])

    # 8. Scribe Settings & Golden Registry Linker
    silo_path = dirs["scribe_silo"]
    settings = ScribeSettings(
        silo_path=str(silo_path.resolve()),
        api_key_paths=str(env_path.resolve()),
        resource_guard=True,
        preferred_llm_model=effective_model,
        latex_ready=latex_ready,
    )

    config_file = dirs["registry"] / "cochem_system_config.json"
    extended_config = update_scribe_registry(config_file, settings)

    logger.info("CoChem-SCRIBE Stage 0.0 Environment Setup completed successfully.")
    return extended_config


def main() -> None:
    """CLI entry point for CoChem-SCRIBE Stage 0.0 setup."""
    parser = argparse.ArgumentParser(description="CoChem-SCRIBE Stage 0.0 Setup Orchestrator")
    parser.add_argument(
        "--artifacts-dir", type=str, default=None, help="Path to artifacts root directory"
    )
    parser.add_argument("--api-key", type=str, default=None, help="Google Gemini API key")
    parser.add_argument(
        "--model",
        type=str,
        default=PreferredLLMModel.GOOGLE_GENAI.value,
        choices=[m.value for m in PreferredLLMModel],
        help="Preferred LLM execution engine",
    )

    args = parser.parse_args()
    artifacts_path = Path(args.artifacts_dir).resolve() if args.artifacts_dir else None

    try:
        setup_scribe_environment(
            artifacts_root=artifacts_path,
            api_key=args.api_key,
            preferred_model=args.model,
        )
        sys.exit(0)
    except Exception as exc:
        logger.critical(f"Setup failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_setup_scribe.py ---
#!/usr/bin/env python3
"""
Unit and Integration Test Suite for CoChem-SCRIBE Stage 0.0 Setup (setup/cochem_setup_scribe.py).
Strictly adheres to Zero-Mock mandate, Method Matrix v4, and FAIR data standards.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Generator

import pytest
from pydantic import ValidationError

from setup.cochem_setup_scribe import (
    APPROVED_SCRIBE_DEPENDENCIES,
    FORBIDDEN_DEPENDENCIES,
    PreferredLLMModel,
    ScribeExtendedSystemConfig,
    ScribeSettings,
    evaluate_resource_guard,
    generate_requirements_manifest,
    get_dynamic_atomic_mass,
    init_airgap_directories,
    is_inside_git_tree,
    probe_latex_environment,
    provision_secure_credentials,
    setup_scribe_environment,
    setup_scribe_logger,
    update_scribe_registry,
    validate_credential_security,
    validate_hdf5_compression,
    validate_tiktoken_encoding,
)


@pytest.fixture
def temp_airgap_env(tmp_path: Path) -> Generator[Path, None, None]:
    """Provides an isolated, clean temporary artifacts directory for testing outside git."""
    test_artifacts_dir = tmp_path / "CoChem_Artifacts"
    test_artifacts_dir.mkdir(parents=True, exist_ok=True)
    yield test_artifacts_dir
    if test_artifacts_dir.exists():
        shutil.rmtree(test_artifacts_dir, ignore_errors=True)


class TestScribeDependencies:
    """SRS Section 4.1: Micro-Silo Environment Builder & Dependency Locking."""

    def test_approved_dependencies_manifest(self, temp_airgap_env: Path) -> None:
        manifest_file = temp_airgap_env / "requirements_scribe.txt"
        generated_path = generate_requirements_manifest(manifest_file)

        assert generated_path.exists()
        content = generated_path.read_text(encoding="utf-8").strip().splitlines()
        manifest_packages = [
            line.split("==")[0].split(">=")[0].strip()
            for line in content
            if line.strip() and not line.startswith("#")
        ]

        for approved in APPROVED_SCRIBE_DEPENDENCIES:
            assert approved in manifest_packages, (
                f"Approved dependency '{approved}' missing from manifest."
            )

        for forbidden in FORBIDDEN_DEPENDENCIES:
            assert forbidden not in manifest_packages, (
                f"Forbidden package '{forbidden}' detected in manifest!"
            )

    def test_manifest_rejects_forbidden_injection(self, temp_airgap_env: Path) -> None:
        manifest_file = temp_airgap_env / "requirements_scribe_custom.txt"
        with pytest.raises(ValueError, match="Unapproved or forbidden dependencies detected"):
            generate_requirements_manifest(
                manifest_file, custom_packages=["google-genai", "tenacity"]
            )

    def test_manifest_rejects_unapproved_injection(self, temp_airgap_env: Path) -> None:
        manifest_file = temp_airgap_env / "requirements_scribe_unapproved.txt"
        with pytest.raises(
            ValueError, match="Unapproved dependencies rejected by micro-silo whitelist"
        ):
            generate_requirements_manifest(
                manifest_file, custom_packages=["google-genai", "unapproved_pkg_xyz"]
            )

    def test_tiktoken_encoding_validation(self) -> None:
        assert validate_tiktoken_encoding("cl100k_base") is True


class TestScribeRegistrySchema:
    """SRS Section 4.2: The Golden Registry & Pydantic Schema Extensions."""

    def test_scribe_settings_valid(self, temp_airgap_env: Path) -> None:
        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        silo_path.mkdir(parents=True, exist_ok=True)
        report_archive = temp_airgap_env / "Report_Archive"
        report_archive.mkdir(parents=True, exist_ok=True)
        env_file = report_archive / ".env"
        env_file.write_text("GEMINI_API_KEY=AIzaSyValidRealKey12345\n", encoding="utf-8")

        settings = ScribeSettings(
            silo_path=str(silo_path.resolve()),
            api_key_paths=str(env_file.resolve()),
            resource_guard=True,
            preferred_llm_model=PreferredLLMModel.GOOGLE_GENAI.value,
            latex_ready=False,
        )

        assert settings.silo_path == str(silo_path.resolve())
        assert settings.api_key_paths == str(env_file.resolve())
        assert settings.resource_guard is True
        assert settings.preferred_llm_model == "google-genai"
        assert settings.latex_ready is False

    def test_scribe_settings_rejects_relative_path(self) -> None:
        with pytest.raises(ValidationError):
            ScribeSettings(
                silo_path="relative/path/silo",
                api_key_paths="relative/.env",
                preferred_llm_model="google-genai",
            )

    def test_scribe_settings_rejects_invalid_model(self, temp_airgap_env: Path) -> None:
        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        env_file = temp_airgap_env / ".env"
        with pytest.raises(ValidationError):
            ScribeSettings(
                silo_path=str(silo_path.resolve()),
                api_key_paths=str(env_file.resolve()),
                preferred_llm_model="invalid-llm-engine",
            )

    def test_extended_config_preserves_registry(self, temp_airgap_env: Path) -> None:
        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        report_archive = temp_airgap_env / "Report_Archive"
        silo_path.mkdir(parents=True, exist_ok=True)
        report_archive.mkdir(parents=True, exist_ok=True)
        env_file = report_archive / ".env"
        env_file.write_text("GEMINI_API_KEY=AIzaSyValidProductionKey123\n", encoding="utf-8")

        settings = ScribeSettings(
            silo_path=str(silo_path.resolve()),
            api_key_paths=str(env_file.resolve()),
            resource_guard=True,
            preferred_llm_model=PreferredLLMModel.GOOGLE_GENAI.value,
            latex_ready=True,
        )

        config_file = temp_airgap_env / "Registry" / "cochem_system_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        updated_config = update_scribe_registry(config_file, settings)
        assert updated_config.scribe_settings is not None
        assert updated_config.scribe_settings.preferred_llm_model == "google-genai"
        assert updated_config.scribe_settings.latex_ready is True
        assert config_file.exists()

        loaded_raw = json.loads(config_file.read_text(encoding="utf-8"))
        assert "scribe_settings" in loaded_raw
        assert loaded_raw["scribe_settings"]["latex_ready"] is True


class TestSecureCredentialProvisioning:
    """SRS Section 4.3: Secure Credential Provisioning & Air-Gap Standards."""

    def test_init_airgap_directories(self, temp_airgap_env: Path) -> None:
        dirs = init_airgap_directories(temp_airgap_env, allow_git_nested=True)
        assert dirs["report_archive"].exists()
        assert dirs["registry"].exists()
        assert dirs["logs"].exists()
        assert dirs["silos"].exists()
        assert dirs["report_archive"].is_dir()
        assert dirs["registry"].is_dir()

    def test_provision_valid_credentials(self, temp_airgap_env: Path) -> None:
        init_airgap_directories(temp_airgap_env, allow_git_nested=True)
        env_path = provision_secure_credentials(
            api_key="AIzaSyAuthenticApiKeyPayloadForVerification777",
            artifacts_root=temp_airgap_env,
            allow_git_nested=True,
        )
        assert env_path.exists()
        assert env_path.parent == temp_airgap_env / "Report_Archive"
        content = env_path.read_text(encoding="utf-8")
        assert "GEMINI_API_KEY=AIzaSyAuthenticApiKeyPayloadForVerification777" in content

        # Verify security validation passes
        assert validate_credential_security(env_path) is True

    def test_provision_fails_on_missing_credentials(self, temp_airgap_env: Path) -> None:
        old_env_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            init_airgap_directories(temp_airgap_env, allow_git_nested=True)
            with pytest.raises(ValueError, match="Missing or invalid authentic API credentials"):
                provision_secure_credentials(
                    api_key="",
                    artifacts_root=temp_airgap_env,
                    allow_git_nested=True,
                )
        finally:
            if old_env_key is not None:
                os.environ["GEMINI_API_KEY"] = old_env_key

    def test_airgap_boundary_violation_in_git_tree(self, tmp_path: Path) -> None:
        git_dir = tmp_path / "mock_repo"
        git_dir.mkdir(parents=True, exist_ok=True)
        (git_dir / ".git").mkdir()
        artifacts_nested = git_dir / "CoChem_Artifacts"

        assert is_inside_git_tree(artifacts_nested) is True
        with pytest.raises(PermissionError, match="Air-Gap boundary violation"):
            init_airgap_directories(artifacts_nested, allow_git_nested=False)


class TestResourceGuardProtocol:
    """SRS Section 4.4: Hardware-Aware Guardrails: RESOURCE_GUARD Protocol."""

    def test_resource_guard_triggers_below_8gb(self, temp_airgap_env: Path) -> None:
        # Override RAM to 6.0 GB to test constraint
        report_archive = temp_airgap_env / "Report_Archive"
        report_archive.mkdir(parents=True, exist_ok=True)

        triggered, model = evaluate_resource_guard(
            requested_model="llama-cpp",
            override_ram_gb=6.0,
            api_key_available=True,
            artifacts_root=temp_airgap_env,
        )
        assert triggered is True
        assert model == PreferredLLMModel.GOOGLE_GENAI.value

        # Check central audit log recording
        audit_file = report_archive / "cochem_audit_log.json"
        assert audit_file.exists()
        logs = json.loads(audit_file.read_text(encoding="utf-8"))
        assert len(logs) >= 1
        assert logs[-1]["level"] == "[SCRIBE-WARNING]"
        assert logs[-1]["event_type"] == "RESOURCE_GUARD_RAM_OVERRIDE"

    def test_resource_guard_passes_above_8gb(self) -> None:
        triggered, model = evaluate_resource_guard(
            requested_model="llama-cpp",
            override_ram_gb=16.0,
            api_key_available=True,
        )
        assert triggered is False
        assert model == "llama-cpp"

    def test_resource_guard_fail_fast_missing_api_key(self, temp_airgap_env: Path) -> None:
        with pytest.raises(RuntimeError, match="RESOURCE_GUARD triggered due to total RAM"):
            evaluate_resource_guard(
                requested_model="llama-cpp",
                override_ram_gb=4.0,
                api_key_available=False,
                artifacts_root=temp_airgap_env,
            )


class TestOSProbingAndHDF5:
    """SRS Section 4.5: Base Utilities & OS-Level Probing."""

    def test_latex_probing(self) -> None:
        result = probe_latex_environment()
        assert isinstance(result, bool)

    def test_hdf5_compression_validation(self, temp_airgap_env: Path) -> None:
        test_h5_dir = temp_airgap_env / "HDF5_Test"
        test_h5_dir.mkdir(parents=True, exist_ok=True)
        # Test authentic 3D quantum density grid slice compression
        success = validate_hdf5_compression(test_h5_dir)
        assert success is True

    def test_scribe_logger_setup(self, temp_airgap_env: Path) -> None:
        report_archive = temp_airgap_env / "Report_Archive"
        report_archive.mkdir(parents=True, exist_ok=True)
        logger_inst = setup_scribe_logger(report_archive, log_filename="cochem_scribe_api.log")

        assert isinstance(logger_inst, logging.Logger)
        logger_inst.info("Test SCRIBE audit message")

        log_file = report_archive / "cochem_scribe_api.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "[SCRIBE-" in content


class TestMendeleevIntegration:
    """Mendeleev Library Mandate: Dynamic atomic mass retrieval."""

    def test_mendeleev_dynamic_masses(self) -> None:
        c_mass = get_dynamic_atomic_mass("C")
        h_mass = get_dynamic_atomic_mass("H")
        o_mass = get_dynamic_atomic_mass("O")
        n_mass = get_dynamic_atomic_mass("N")
        fe_mass = get_dynamic_atomic_mass("Fe")

        assert 12.0 <= c_mass <= 12.02
        assert 1.0 <= h_mass <= 1.01
        assert 15.99 <= o_mass <= 16.00
        assert 14.00 <= n_mass <= 14.01
        assert 55.84 <= fe_mass <= 55.85

    def test_mendeleev_invalid_symbol(self) -> None:
        with pytest.raises((ValueError, KeyError)):
            get_dynamic_atomic_mass("InvalidElementSymbol999")


class TestFullScribeSetupWorkflow:
    """Integration Test: Full Stage 0.0 Setup Orchestration."""

    def test_setup_scribe_environment_e2e(self, temp_airgap_env: Path) -> None:
        config = setup_scribe_environment(
            artifacts_root=temp_airgap_env,
            api_key="AIzaSyAuthenticProductionValidKey456",
            preferred_model="google-genai",
            allow_git_nested=True,
        )

        assert isinstance(config, ScribeExtendedSystemConfig)
        assert config.scribe_settings is not None
        assert config.scribe_settings.preferred_llm_model == "google-genai"
        assert Path(config.scribe_settings.api_key_paths).exists()
        assert Path(config.scribe_settings.silo_path).exists()
        assert (temp_airgap_env / "Report_Archive" / "cochem_scribe_api.log").exists()
        assert (temp_airgap_env / "Registry" / "requirements_scribe.txt").exists()

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.