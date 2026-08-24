Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\02_cochem_scribe_master.md.
Original prompt:
# CoChem-SCRIBE Implementation Prompt: cochem_scribe_master.py

## Context
You are a coding agent tasked with implementing a specific module for CoChem-SCRIBE.
The target repository path is: `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`.
The file you must implement is: `core/cochem_scribe_master.py`.

## Authoritative Reference
This implementation is strictly governed by **Phase 4, Task 11: Master Orchestration, Assembly, & CI/CD (Stage 6.0/6.3)** and **Phase 1, Task 2 (Section 2.2)** of the CoChem-SCRIBE Software Requirements Specification (SRS), adhering to Method Matrix v4, FAIR data principles, the Zero-Mock Anti-Spoofing Protocol, and the 6-Tier Environment Matrix (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC).

---

## Ecosystem Role & Deliverable Capabilities

`core/cochem_scribe_master.py` is the Stage 6.0 Master Orchestrator, CLI Entry Point, and Integration Hub for the entire CoChem-SCRIBE reporting and synthesis pipeline across all 6 target execution tiers.

### 1. Master Orchestrator Architecture (`ScribeOrchestrator`) (SRS Tasks 91 & 92)
- Define the `ScribeOrchestrator` class that coordinates and integrates the following 5 core subsystem modules:
  1. `DataAggregator` (`harvesters.scribe_aggregator`): Single-Writer/Multiple-Reader (SWMR) HDF5 data extraction and telemetry harvester.
  2. `PayloadBuilder` (`harvesters.scribe_payload_builder`): Context compression, dynamic token metrology (`tiktoken` `cl100k_base`), and prompt synthesizer.
  3. `ScribeLLMEngine` / `ScribeInference` (`engines.scribe_engine` / `engines.scribe_inference`): Hardware-routed inference engine (`RESOURCE_GUARD` routing between local `.gguf` and API modes).
  4. `Jinja2Templater` (`formatters.scribe_templater`): Mathematical Air-Gap LaTeX/Markdown scaffold injection.
  5. `DocumentManager` (`managers.scribe_doc_manager`): Headless multi-pass LaTeX compilation (`pdflatex -> bibtex -> pdflatex -> pdflatex`), ZIP packaging, and POSIX permission locking.
- **Strict 5-Step Sequential Pipeline Loop:**
  Enforce explicit sequential execution with typed inter-stage data contracts:
  - `[1/5] Harvest HDF5`: Extract numerical tensors, thermodynamic quantities, and telemetry from input database (`landscape.h5`).
  - `[2/5] Build Payload`: Compress numerical arrays and synthesize structured prompts within token limits ($\le 6,000$ tokens).
  - `[3/5] LLM Inference`: Execute hardware-safe inference or handle authentic `--dry-run` fallback methodology strings.
  - `[4/5] Template Docs`: Inject unaltered empirical data arrays post-inference into LaTeX/Markdown Jinja2 templates.
  - `[5/5] Compile & Zip`: Execute silent headless compilation, clean build waste, write `manifest.json`, bundle into `CoChem_Final_Report_[TIMESTAMP].zip`, and apply POSIX `0o444` read-only lock.

### 2. CLI Integration & Dynamic Air-Gap Pathing (SRS Task 93)
- Utilize `argparse` to provide a robust command-line interface supporting standard arguments:
  - `--config-path` (`pathlib.Path`): Defaults dynamically to `pathlib.Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json"`.
  - `--output-dir` (`pathlib.Path`): Defaults dynamically to `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"`.
  - `--h5-path` (`pathlib.Path`): Defaults dynamically to `pathlib.Path.home() / "CoChem_Artifacts" / "Calculations" / "landscape.h5"`.
  - `--dry-run` (`bool`): Flag enabling end-to-end dry-run execution without hitting remote network APIs.
  - `--model-engine` (`str`, optional): Override for engine selection (`gemini`, `local-llama`, `dry-run`).
- **Air-Gap Mandate:** All configuration, log, calculation, and output paths MUST be resolved dynamically via `pathlib.Path.home()`. Hardcoded absolute paths or writing ephemeral data into the Git repository tree is strictly prohibited.

### 3. Visual Progress Tracking & Headless TTY Guard (SRS Task 94)
- Wrap the 5-step pipeline execution in a terminal-safe progress indicator (`rich.progress` or `tqdm`).
- **Headless TTY Detection:** Automatically detect whether standard output is attached to an interactive terminal (`sys.stdout.isatty()`).
  - If interactive (`sys.stdout.isatty() == True`): Render visual progress bar.
  - If headless/non-interactive (`sys.stdout.isatty() == False`, e.g., SLURM/PBS HPC logs, GitHub Actions CI runners): Disable escape-code animation (`disable=True` or emit discrete text log markers `[SCRIBE-INFO] [Step X/5] ...`) to prevent log corruption.

### 4. Fatal Exception Catcher & Safe Process Termination (SRS Task 95)
- Wrap the entire orchestrator execution loop in a top-level `try/except Exception` block.
- In the event of a fatal, unrecoverable crash:
  - Intercept the exception and format a complete stack trace.
  - Safely write/append the failure telemetry to the Air-Gapped audit log at `pathlib.Path.home() / "CoChem_Artifacts" / "cochem_audit_log.json"`.
  - Perform clean environment teardown (releasing open file handles or resources).
  - Terminate the process cleanly with exit code 1 (`sys.exit(1)`) to ensure HPC schedulers (SLURM/PBS) and CI/CD pipelines (GitHub Actions) properly record the failure without crashing or hanging the parent compute queue.

### 5. Deterministic Codebase SHA-256 Topological Hasher (SRS Task 100)
- Implement a dedicated function to generate a cryptographic SHA-256 hash representing the topological state of the `CoChem-SCRIBE` repository:
  1. Recursively scan the repository root for all tracked source files (e.g., `.py`, `.json`, `.yaml`, `.yml`, `.md`, `.tex`).
  2. Exclude ephemeral, cache, and virtual environment directories: `__pycache__`, `.git`, `.venv`, `venv`, `.pytest_cache`, `.eggs`, `*.egg-info`, `dist`, `build`.
  3. Sort relative file paths alphabetically to guarantee cross-platform deterministic order across Windows (WSL), macOS (OrbStack), and Linux (Debian/HPC).
  4. Stream and hash the normalized content bytes of each file into a master SHA-256 digest.
  5. Permanently bind the computed topological hash into the generated `manifest.json` and pass it to the execution telemetry for immutable FAIR provenance tracking.

---

## Directives & Execution Constraints

1. **Single File Output:** Output only this single Python file (`core/cochem_scribe_master.py`). Do not implement other files in this prompt.
2. **Zero-Mock Anti-Spoofing Protocol:** Strictly NO mocks, stubs, dummy functions, synthetic test strings, or fake logic.
   - Do NOT use `unittest.mock` or `MagicMock`.
   - The `--dry-run` mode must execute the genuine sequential pipeline passes using static fallback methodology strings without hitting live network APIs, rather than returning a faked or empty execution.
3. **Strict Typing & Error Handling:** Use Python 3.10+ type hints (`pathlib.Path`, `dict[str, Any]`, `Optional[str]`, etc.), Pydantic models where appropriate, and standard `logging` with `[SCRIBE-*]` prefixes.
4. **Air-Gap Compliance:** Dynamic path resolution via `pathlib.Path.home()`. No hardcoded OS-specific paths.
5. **Adhere Strictly to CoChem Standards:**
   - Method Matrix v4 constraints.
   - Support the 6-Tier Environment Matrix (WSL, OrbStack, Debian, Codespaces, GitHub Actions, HPC).
   - Strict adherence to FAIR data principles (Findable, Accessible, Interoperable, Reusable).
6. **No External Scripting:** Ensure no external Python orchestration scripts are used in document generation.

---

## Task
Implement the Python module as described and save it to `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\core\cochem_scribe_master.py` using the `write_to_file` tool.

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
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import h5py
import numpy as np
import psutil
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


def setup_scribe_logger(log_dir: Optional[Path] = None) -> logging.Logger:
    """
    Initializes the CoChem-SCRIBE central logger with [SCRIBE-*] log prefixes
    and a RotatingFileHandler to monitor and audit operations.
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
        log_file = log_dir_path / "scribe_audit.log"
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

    silo_path: str = Field(..., description="Absolute path to the scribe_llm environment or Python executable")
    api_key_paths: str = Field(..., description="Absolute path to the secure .env file in the Data Tier")
    resource_guard: bool = Field(default=True, description="Hardware resource guard flag")
    preferred_llm_model: str = Field(default=PreferredLLMModel.GOOGLE_GENAI.value, description="Preferred LLM model")
    latex_ready: bool = Field(default=False, description="Dynamic boolean set during pre-flight OS probing")

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
            raise ValueError(f"Relative paths are strictly forbidden in ScribeSettings: '{v}'. Must be absolute.")
        return str(p)


if CoChemSystemConfig is not None:
    class ScribeExtendedSystemConfig(CoChemSystemConfig):  # type: ignore
        """
        Master Golden Registry extension containing dedicated scribe_settings
        without invalidating upstream CoChem-BASE schema fields.
        """
        model_config = ConfigDict(extra="forbid", validate_assignment=True)
        scribe_settings: Optional[ScribeSettings] = Field(default=None, description="CoChem-SCRIBE configuration")
else:
    class ScribeExtendedSystemConfig(BaseModel):  # type: ignore
        """Fallback standalone configuration schema if CoChemSystemConfig base is unresolvable."""
        model_config = ConfigDict(extra="allow", validate_assignment=True)
        schema_version: str = Field(default="4.0.0")
        registry_checksum: Optional[str] = Field(default="")
        scribe_settings: Optional[ScribeSettings] = Field(default=None, description="CoChem-SCRIBE configuration")


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
            pkg for pkg in custom_packages
            if any(fb in _normalize_pkg_name(pkg) for fb in FORBIDDEN_DEPENDENCIES)
        ]
        if forbidden:
            raise ValueError(f"Unapproved or forbidden dependencies detected in manifest generation: {forbidden}")

        unapproved = [
            pkg for pkg in custom_packages
            if _normalize_pkg_name(pkg) not in approved_base_set
        ]
        if unapproved:
            raise ValueError(f"Unapproved dependencies rejected by micro-silo whitelist: {unapproved}")

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
        raise PermissionError(f"Security validation failed: Process cannot read credential file at {env_path}")

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
    Generates the .env file exclusively inside the Air-Gapped output directory ($HOME/CoChem_Artifacts/).
    Populates exclusively with authentic, validated credential payloads.
    Fails fast upon missing credentials.
    """
    root = Path(artifacts_root).resolve() if artifacts_root else get_cochem_artifacts_dir()

    if not allow_git_nested and is_inside_git_tree(root):
        raise PermissionError(
            f"Air-Gap boundary violation: Cannot provision credentials in '{root}' because it is inside a Git repository."
        )

    os.makedirs(root, exist_ok=True)
    env_path = root / env_filename

    resolved_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    resolved_key = resolved_key.strip()

    if not resolved_key or resolved_key.lower() in DISALLOWED_KEY_PATTERNS or len(resolved_key) < 10:
        raise ValueError("Missing or invalid authentic API credentials. GEMINI_API_KEY must be provided and authentic.")

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

def evaluate_resource_guard(
    requested_model: str = PreferredLLMModel.LLAMA_CPP.value,
    override_ram_gb: Optional[float] = None,
    api_key_available: Optional[bool] = None,
    artifacts_root: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    Evaluates host RAM against the 8.0 GB threshold.
    If RAM < 8.0 GB, triggers RESOURCE_GUARD, forces state override to 'google-genai',
    and fails fast if API credentials are missing.
    """
    if override_ram_gb is not None:
        total_ram_gb = float(override_ram_gb)
    else:
        total_ram_gb = psutil.virtual_memory().total / (1024.0 ** 3)

    if total_ram_gb < RESOURCE_GUARD_RAM_THRESHOLD_GB:
        logger.warning(
            f"System RAM ({total_ram_gb:.2f} GB) < {RESOURCE_GUARD_RAM_THRESHOLD_GB} GB threshold. "
            "RESOURCE_GUARD triggered: Forcefully routing execution state to 'google-genai'."
        )

        # Check API key availability authentically
        if api_key_available is None:
            api_key_env = os.environ.get("GEMINI_API_KEY", "").strip()
            root = Path(artifacts_root).resolve() if artifacts_root else get_cochem_artifacts_dir()
            artifacts_env = root / ".env"
            has_file_key = False
            if artifacts_env.exists():
                try:
                    for line in artifacts_env.read_text(encoding="utf-8").splitlines():
                        if line.startswith("GEMINI_API_KEY="):
                            val = line.split("=", 1)[1].strip()
                            if val and val.lower() not in DISALLOWED_KEY_PATTERNS and len(val) >= 10:
                                has_file_key = True
                                break
                except Exception:
                    pass
            has_env_key = bool(api_key_env and api_key_env.lower() not in DISALLOWED_KEY_PATTERNS and len(api_key_env) >= 10)
            api_key_available = has_env_key or has_file_key

        if not api_key_available:
            raise RuntimeError(
                f"RESOURCE_GUARD triggered due to total RAM ({total_ram_gb:.2f} GB < 8.0 GB), "
                "forcing API mode ('google-genai'), but authentic GEMINI_API_KEY is missing. "
                "Aborting initialization."
            )

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
        raise ValueError(f"Could not retrieve atomic mass for element symbol '{symbol}' from mendeleev.")
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
                raise ValueError("HDF5 data integrity mismatch during gzip+shuffle+fletcher32 round-trip.")

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
            logger.warning(f"Error parsing existing registry at {config_path} ({exc}); initializing fresh configuration.")
            extended_config = _create_fresh_extended_config(scribe_settings)
    else:
        extended_config = _create_fresh_extended_config(scribe_settings)

    # Compute deterministic SHA-256 checksum
    serialized_dict = extended_config.model_dump(exclude={"registry_checksum", "last_updated"})
    cs = hashlib.sha256(json.dumps(serialized_dict, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    extended_config.registry_checksum = cs

    # Atomic write to filesystem via temporary staging file and os.replace (HPC & Clustered safe)
    temp_file = config_path.parent / f".tmp_{config_path.name}_{uuid.uuid4().hex[:8]}"
    temp_file.write_text(extended_config.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temp_file, config_path)

    logger.info(f"Golden Registry successfully updated and atomic-locked at: {config_path}")
    return extended_config


def _create_fresh_extended_config(scribe_settings: Optional[ScribeSettings]) -> ScribeExtendedSystemConfig:
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
    2. Generates locked requirements manifest (requirements_scribe.txt).
    3. Provisions authentic credentials (.env) with POSIX 0o600 privilege lock.
    4. Evaluates hardware against RESOURCE_GUARD protocol (< 8.0 GB RAM constraint).
    5. Probes OS environment for LaTeX (pdflatex/xelatex).
    6. Validates HDF5 Method Matrix v4 compression pipeline (gzip+shuffle+fletcher32).
    7. Updates Golden Registry with Pydantic-validated scribe_settings atomically.
    """
    # 1. Directory Structure
    dirs = init_airgap_directories(artifacts_root, allow_git_nested=allow_git_nested)
    log_dir = dirs["logs"]
    setup_scribe_logger(log_dir)

    logger.info("Initializing CoChem-SCRIBE Stage 0.0 Environment Setup...")

    # 2. Dependency Locking
    manifest_path = dirs["registry"] / "requirements_scribe.txt"
    generate_requirements_manifest(manifest_path)

    # 3. Secure Credentials
    env_path = provision_secure_credentials(
        api_key=api_key,
        artifacts_root=dirs["root"],
        allow_git_nested=allow_git_nested,
    )

    # 4. Hardware Resource Guard
    _, effective_model = evaluate_resource_guard(
        requested_model=preferred_model,
        artifacts_root=dirs["root"],
    )

    # 5. OS LaTeX Probing
    latex_ready = probe_latex_environment()

    # 6. HDF5 Compression Validation
    validate_hdf5_compression(log_dir)

    # 7. Scribe Settings & Golden Registry Linker
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
    parser.add_argument("--artifacts-dir", type=str, default=None, help="Path to artifacts root directory")
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_scribe_master.py ---
#!/usr/bin/env python3
"""
Unit and Integration Test Suite for CoChem-SCRIBE Stage 6.0 Master Orchestrator
(core/cochem_scribe_master.py).
Strictly adheres to the Zero-Mock mandate, Method Matrix v4, and FAIR data standards.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Generator

import h5py
import numpy as np
import pytest
from pydantic import ValidationError

from core.cochem_scribe_master import (
    MAX_PAYLOAD_TOKENS,
    PreferredEngine,
    DataAggregator,
    PayloadBuilder,
    ScribeLLMEngine,
    Jinja2Templater,
    DocumentManager,
    ScribeOrchestrator,
    ScribeOrchestrationConfig,
    ScribeProgressTracker,
    ConformerRecord,
    HarvestedData,
    CompressedPayload,
    InferenceResult,
    TemplatedDocuments,
    CompilationResult,
    compute_codebase_topological_hash,
    get_dynamic_atomic_mass,
    parse_cli_args,
    record_fatal_crash,
)


@pytest.fixture
def temp_airgap_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Provides an isolated, clean temporary directory for testing."""
    test_dir = tmp_path / "CoChem_Test_Workspace"
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def sample_hdf5_landscape(temp_airgap_workspace: Path) -> Path:
    """Generates an authentic HDF5 test database with real conformer energetics and grid tensors."""
    h5_path = temp_airgap_workspace / "landscape.h5"
    with h5py.File(str(h5_path), "w") as f:
        f.attrs["compute_flags"] = json.dumps(["MPQC_4", "MACE_OFF24m", "CCSD(T)-F12"])
        f.attrs["lam_trigger"] = 0

        # Conformer 1: Global minimum
        g1 = f.create_group("conformer_01_anti")
        g1.attrs["electronic_energy"] = -154.234567
        g1.attrs["enthalpy"] = -154.120000
        g1.attrs["gibbs_free_energy"] = -154.150000
        g1.attrs["zero_point_energy"] = 0.114567
        g1.attrs["rotational_constants"] = [10245.5, 4321.2, 3105.8]
        g1.attrs["dipole_moment"] = 1.85
        g1.attrs["method"] = "CCSD(T)-F12"
        g1.attrs["basis_set"] = "cc-pVTZ-F12"

        # Conformer 2: Local minimum
        g2 = f.create_group("conformer_02_gauche")
        g2.attrs["electronic_energy"] = -154.230123
        g2.attrs["enthalpy"] = -154.115000
        g2.attrs["gibbs_free_energy"] = -154.145000
        g2.attrs["zero_point_energy"] = 0.115123
        g2.attrs["rotational_constants"] = [9876.4, 4567.1, 3210.5]
        g2.attrs["dipole_moment"] = 2.45
        g2.attrs["method"] = "r2SCAN-3c"

        # State tensor dataset
        grid_data = np.linspace(-2.5, 2.5, 64, dtype=np.float64)
        f.create_dataset("density_grid", data=grid_data)

    return h5_path


class TestDataAggregator:
    """SRS Task 91: DataAggregator SWMR Extraction and Telemetry Harvester."""

    def test_harvest_valid_hdf5(self, sample_hdf5_landscape: Path) -> None:
        aggregator = DataAggregator(h5_path=sample_hdf5_landscape)
        harvested = aggregator.harvest()

        assert isinstance(harvested, HarvestedData)
        assert len(harvested.conformers) == 2
        assert harvested.conformers[0].name == "conformer_01_anti"
        assert harvested.conformers[0].electronic_energy_hartree == pytest.approx(-154.234567)
        assert len(harvested.conformers[0].rotational_constants_mhz) == 3
        assert "MPQC_4" in harvested.compute_flags
        assert "MACE_OFF24m" in harvested.compute_flags
        assert len(harvested.state_tensor_provenance_hash) == 64
        assert harvested.grid_points_count == 64

    def test_harvest_missing_hdf5_fallback(self, temp_airgap_workspace: Path) -> None:
        missing_h5 = temp_airgap_workspace / "nonexistent.h5"
        aggregator = DataAggregator(h5_path=missing_h5)
        harvested = aggregator.harvest()

        assert isinstance(harvested, HarvestedData)
        assert len(harvested.conformers) == 0
        assert len(harvested.compute_flags) == 0
        assert len(harvested.state_tensor_provenance_hash) == 64


class TestPayloadBuilder:
    """SRS Task 91: PayloadBuilder Context Compression & Token Metrology."""

    def test_token_counting_and_prompt_synthesis(self, sample_hdf5_landscape: Path) -> None:
        aggregator = DataAggregator(h5_path=sample_hdf5_landscape)
        harvested = aggregator.harvest()

        builder = PayloadBuilder(max_tokens=MAX_PAYLOAD_TOKENS)
        payload = builder.build_payload(harvested, system_config={"hardware": {"ram_gb": 32.0}})

        assert isinstance(payload, CompressedPayload)
        assert payload.token_count > 0
        assert payload.token_count <= MAX_PAYLOAD_TOKENS
        assert payload.is_within_budget is True
        assert "conformer_01_anti" in payload.synthesized_prompt
        assert "State Tensor Provenance Digest" in payload.synthesized_prompt

    def test_payload_compression_on_large_input(self, temp_airgap_workspace: Path) -> None:
        builder = PayloadBuilder(max_tokens=200)
        confs = [
            ConformerRecord(
                name=f"conf_{i:03d}",
                electronic_energy_hartree=-100.0 - i * 0.001,
                enthalpy_hartree=-99.9 - i * 0.001,
                gibbs_free_energy_hartree=-99.8 - i * 0.001,
                rotational_constants_mhz=[1000.0, 500.0, 250.0],
                provenance_tag="[D]",
            )
            for i in range(50)
        ]
        harvested = HarvestedData(
            database_path=str(temp_airgap_workspace / "test.h5"),
            conformers=confs,
            compute_flags=["MPQC_4"],
            software_versions=[],
            lam_trigger_required=False,
            grid_points_count=100,
            state_tensor_provenance_hash="abc123hash",
            harvest_timestamp="2026-08-24T12:00:00Z",
        )
        payload = builder.build_payload(harvested)
        assert isinstance(payload, CompressedPayload)
        assert payload.compressed_conformer_count == 50


class TestScribeLLMEngine:
    """SRS Task 91: ScribeLLMEngine Hardware Routing & Authentic Dry-Run."""

    def test_dry_run_synthesis(self, sample_hdf5_landscape: Path) -> None:
        aggregator = DataAggregator(h5_path=sample_hdf5_landscape)
        harvested = aggregator.harvest()
        builder = PayloadBuilder()
        payload = builder.build_payload(harvested)

        engine = ScribeLLMEngine(preferred_engine=PreferredEngine.DRY_RUN.value, dry_run=True)
        res = engine.execute_inference(payload)

        assert isinstance(res, InferenceResult)
        assert res.is_dry_run is True
        assert res.engine_used == "dry-run"
        assert "Electronic structure calculations" in res.methodology_text
        assert "MPQC 4.0" in res.methodology_text
        assert "CoChem-SCRIBE User Guide" in res.user_guide_markdown
        assert "Results and Discussion" in res.results_discussion_markdown


class TestJinja2Templater:
    """SRS Task 91: Jinja2Templater Air-Gap LaTeX and Markdown Rendering."""

    def test_render_all_templates(self, sample_hdf5_landscape: Path, temp_airgap_workspace: Path) -> None:
        aggregator = DataAggregator(h5_path=sample_hdf5_landscape)
        harvested = aggregator.harvest()
        builder = PayloadBuilder()
        payload = builder.build_payload(harvested)
        engine = ScribeLLMEngine(dry_run=True)
        inf_res = engine.execute_inference(payload)

        output_dir = temp_airgap_workspace / "Templated_Output"
        templater = Jinja2Templater(output_dir=output_dir)
        templated_docs = templater.render_templates(harvested, inf_res)

        assert isinstance(templated_docs, TemplatedDocuments)
        assert Path(templated_docs.methodology_tex_path).exists()
        assert Path(templated_docs.references_bib_path).exists()
        assert Path(templated_docs.manuscript_tables_tex_path).exists()
        assert Path(templated_docs.user_guide_md_path).exists()
        assert Path(templated_docs.results_discussion_md_path).exists()

        methods_content = Path(templated_docs.methodology_tex_path).read_text(encoding="utf-8")
        assert "\\usepackage{siunitx}" in methods_content
        assert "[M]" in methods_content or "[D]" in methods_content

        tables_content = Path(templated_docs.manuscript_tables_tex_path).read_text(encoding="utf-8")
        assert "\\begin{table}" in tables_content
        assert "conformer_01_anti" in tables_content
        assert "0.00" in tables_content


class TestDocumentManager:
    """SRS Task 91 & 92: DocumentManager Headless Compilation & ZIP Archival."""

    def test_compile_manifest_and_zip_bundle(
        self, sample_hdf5_landscape: Path, temp_airgap_workspace: Path
    ) -> None:
        aggregator = DataAggregator(h5_path=sample_hdf5_landscape)
        harvested = aggregator.harvest()
        builder = PayloadBuilder()
        payload = builder.build_payload(harvested)
        engine = ScribeLLMEngine(dry_run=True)
        inf_res = engine.execute_inference(payload)

        output_dir = temp_airgap_workspace / "Report_Output"
        templater = Jinja2Templater(output_dir=output_dir)
        templated_docs = templater.render_templates(harvested, inf_res)

        topo_hash = compute_codebase_topological_hash()
        doc_mgr = DocumentManager(output_dir=output_dir)
        comp_res = doc_mgr.compile_and_package(templated_docs, harvested, topo_hash)

        assert isinstance(comp_res, CompilationResult)
        assert Path(comp_res.final_zip_path).exists()
        assert Path(comp_res.manifest_path).exists()
        assert len(comp_res.zip_sha256) == 64
        assert comp_res.codebase_topological_hash == topo_hash
        assert comp_res.total_archived_files > 0

        with zipfile.ZipFile(comp_res.final_zip_path, "r") as zf:
            namelist = zf.namelist()
            assert "Methodology.tex" in namelist
            assert "manuscript_tables.tex" in namelist
            assert "references.bib" in namelist
            assert "manifest.json" in namelist

        manifest_raw = json.loads(Path(comp_res.manifest_path).read_text(encoding="utf-8"))
        assert "codebase_topological_hash" in manifest_raw
        assert manifest_raw["codebase_topological_hash"] == topo_hash
        assert "archived_artifacts" in manifest_raw


class TestTopologicalHasher:
    """SRS Task 100: Deterministic Codebase SHA-256 Topological Hasher."""

    def test_topological_hasher_determinism(self, temp_airgap_workspace: Path) -> None:
        repo_dir = temp_airgap_workspace / "mock_codebase"
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / "module_a.py").write_text("print('alpha')\n", encoding="utf-8")
        (repo_dir / "module_b.py").write_text("print('beta')\n", encoding="utf-8")
        (repo_dir / "data.json").write_text("{\"key\": 1}\n", encoding="utf-8")

        pycache_dir = repo_dir / "__pycache__"
        pycache_dir.mkdir(parents=True, exist_ok=True)
        (pycache_dir / "cache_file.pyc").write_text("ephemeral", encoding="utf-8")

        digest1 = compute_codebase_topological_hash(repo_dir)
        digest2 = compute_codebase_topological_hash(repo_dir)
        assert len(digest1) == 64
        assert digest1 == digest2

        (repo_dir / "module_a.py").write_text("print('alpha_modified')\n", encoding="utf-8")
        digest3 = compute_codebase_topological_hash(repo_dir)
        assert digest1 != digest3


class TestScribeOrchestratorPipeline:
    """Integration: Full 5-Step Sequential Pipeline Execution."""

    def test_full_pipeline_run_dry_run(
        self, sample_hdf5_landscape: Path, temp_airgap_workspace: Path
    ) -> None:
        out_dir = temp_airgap_workspace / "Full_Pipeline_Archive"
        config = ScribeOrchestrationConfig(
            config_path=temp_airgap_workspace / "cochem_system_config.json",
            output_dir=out_dir,
            h5_path=sample_hdf5_landscape,
            dry_run=True,
            model_engine=PreferredEngine.DRY_RUN.value,
        )

        orchestrator = ScribeOrchestrator(config=config)
        res = orchestrator.run_pipeline()

        assert isinstance(res, CompilationResult)
        assert Path(res.final_zip_path).exists()
        assert Path(res.manifest_path).exists()
        assert res.total_archived_files >= 5

    def test_progress_tracker_non_interactive(self) -> None:
        tracker = ScribeProgressTracker(total_steps=5)
        tracker.step(1, "Testing Step 1")
        tracker.step(2, "Testing Step 2")

    def test_cli_argument_parsing(self, temp_airgap_workspace: Path) -> None:
        args = parse_cli_args([
            "--output-dir", str(temp_airgap_workspace / "cli_out"),
            "--dry-run",
            "--model-engine", "dry-run",
        ])
        assert args.dry_run is True
        assert args.model_engine == "dry-run"
        assert args.output_dir == temp_airgap_workspace / "cli_out"


class TestFatalExceptionCatcher:
    """SRS Task 95: Fatal Exception Catcher & Safe Process Termination."""

    def test_record_fatal_crash(self, temp_airgap_workspace: Path) -> None:
        audit_file = temp_airgap_workspace / "cochem_audit_log.json"
        try:
            raise RuntimeError("Synthetic test error for fatal exception verification")
        except RuntimeError as err:
            record_fatal_crash(err, audit_log_path=audit_file)

        assert audit_file.exists()
        log_entries = json.loads(audit_file.read_text(encoding="utf-8"))
        assert len(log_entries) >= 1
        last_entry = log_entries[-1]
        assert last_entry["event_type"] == "FATAL_ORCHESTRATION_EXCEPTION"
        assert last_entry["exception_type"] == "RuntimeError"
        assert "Synthetic test error" in last_entry["exception_message"]
        assert "traceback" in last_entry


class TestMendeleevIntegration:
    """Mendeleev Library Mandate: Dynamic atomic mass retrieval."""

    def test_dynamic_mass_retrieval(self) -> None:
        c_mass = get_dynamic_atomic_mass("C")
        h_mass = get_dynamic_atomic_mass("H")
        n_mass = get_dynamic_atomic_mass("N")
        assert 12.0 <= c_mass <= 12.02
        assert 1.0 <= h_mass <= 1.01
        assert 14.0 <= n_mass <= 14.02

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.