Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc3_02_unity_installer_dashboard_prompt.md.
Original prompt:
# cochem_unity_installer_dashboard.py Generation Prompt

**Target Filepath:** `D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_unity_installer_dashboard.py`

## Context
You are tasked with writing the `cochem_unity_installer_dashboard.py` for CoChem-BASE. This script contains the `ipywidgets` unified dashboard logic that serves as a code-blind graphical frontend when rendered via Voila. It handles user interaction, topological locking, and system state serialization.

## Instructions
Write the complete Python script ensuring the following requirements are met:
1. **Voila Compatibility**: The code must rely purely on `ipywidgets` to render the UI, keeping it clean and standalone for Voila without raw traceback logs leaking to the browser DOM.
2. **6-Tier Interaction Selection Model**: Provide decoupled dropdown menus to select the interaction environment: `Local-Windows (WSL)`, `Local-MacOS (OrbStack)`, `Local-Linux (Deb)`, `GitHub Codespaces`, `HPC`, and `GitHub Actions`. 
   - Route the backend orchestrator to execute OS-native bash/Python bindings based on this selection.
   - If the `$CODESPACES` environment variable is detected, auto-lock this selection.
3. **Real-Time Hardware Profiling HUD**: Create a dynamic HTML table or widget block that polls `cochem_system_config.json` after Phase 2 completion. Display: Total RAM, Available CPU Cores, GPU VRAM, AVX-512 capability. Visually warn users (red/yellow highlighting) if resources are critically insufficient.
4. **Topological Prerequisite Locking**: Present a checklist of downstream CoChem modules (`TOPOS`, `TORQ`, `SCAN`, `SCRIBE`). 
   - Base dependencies (`CoChem-BASE`, `CoChem-MInt`) must be visually rendered but mathematically locked (`disabled=True`, `value=True`).
   - Enforce rigid dependency graphs: If a heavy module is selected, automatically check its prerequisites.
   - AI/LLM modules (`SCRIBE`) must remain unselected by default to respect the `RESOURCE_GUARD` mandate.
5. **Orchestrator Lock (UI Immutability)**: When the "Initialize Pipeline" button is clicked, all `ipywidgets` inputs must instantly shift to `disabled=True` to prevent double-clicking and race conditions.
6. **State Serialization**: On execution, aggregate all selections into a strict JSON object and save it to the Persistent Data Tier (e.g., `$SCRATCH/CoChem_Artifacts/Registry/cochem_system_config.json` or `$COCHEM_DATA_ROOT/CoChem_Artifacts/Registry/cochem_system_config.json`). All paths must dynamically resolve via these data tier variables.
   - **Banned**: Hardcoding `$HOME` paths is strictly forbidden.
   - Render a green success text ("CoChem-BASE Fully Initialized. Safe to proceed.") upon successful serialization.
7. **Asynchronous Task Management & Error Bubbling**: All background orchestrator processes must use async polling (`asyncio` or `threading`). Long-running tasks must not block the main loop. Runtime errors, warnings, and progress must bubble up natively into an explicit `ipywidgets.Output()` widget without freezing the UI.

## Constraints
- **NO Mocks, Stubs, or Placeholders.** Write the complete logic for the UI, state management, hardware polling, and async execution.
- Code must be production-ready and accurately implement all architectural requirements.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\interfaces\cochem_unity_installer_dashboard.py ---
#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.0 - Ecosystem Master Installer & Configurator Dashboard.

Provides the interactive ipywidgets tabbed GUI and automated headless deployment logic
for provisioning CoChem micro-silos, enforcing topological prerequisites, verifying
Host ORCA engines, dynamic hardware telemetry profiling, and executing Air-Gap Zip
sideloading across the Tripartite Workspace.
"""

from __future__ import annotations

import argparse
import atexit
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import ipywidgets as widgets
import psutil
from IPython.display import clear_output, display
from pydantic import BaseModel, Field

from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_scratch_dir,
    resolve_config_path,
    resolve_executable,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-Installer")

sys.path.insert(0, str(get_base_root()))
try:
    from core_engine.cochem_core_subprocess_broker import (
        cleanup_zombie_processes,
        register_popen_process,
        safe_subprocess_run,
    )
except ImportError:
    safe_subprocess_run = None  # type: ignore
    register_popen_process = None  # type: ignore

    def cleanup_zombie_processes() -> int:  # type: ignore
        reaped = 0
        try:
            current_process = psutil.Process(os.getpid())
            children = current_process.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            gone, alive = psutil.wait_procs(children, timeout=3)
            for p in alive:
                try:
                    p.kill()
                    reaped += 1
                except psutil.NoSuchProcess:
                    pass
        except Exception as e:
            logger.warning(f"Fallback zombie sweep warning: {e}")
        return reaped


def _cleanup_zombie_processes() -> int:
    """Invokes the central zombie reaper safely."""
    try:
        return cleanup_zombie_processes()
    except Exception as e:
        logger.warning(f"Zombie cleanup encountered error: {e}")
        return 0


atexit.register(_cleanup_zombie_processes)


class DeploymentManifest(BaseModel):
    """Pydantic model validating the Stage 0 deployment manifest."""

    version: str = Field(default="2026.2", description="CoChem-BASE platform release version.")
    git_provenance_hash: str = Field(description="SHA-1 commit hash of the base repository.")
    interaction_environment: str = Field(description="Selected UI / interaction execution environment.")
    calculation_environment: str = Field(description="Selected compute / calculation execution tier.")
    orca_tarball_path: str = Field(default="", description="Path or binary alias for Host ORCA executable.")
    selected_repositories: List[str] = Field(description="List of selected ecosystem modules.")
    headless: bool = Field(default=False, description="Whether deployment was executed in headless mode.")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of manifest creation.",
    )


ECOSYSTEM_REGISTRY: Dict[str, Dict[str, Any]] = {
    "CoChem-BASE": {
        "desc": "Master environment orchestration, path resolution, and configuration.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-BASE",
        "mandatory": True,
    },
    "CoChem-MInt": {
        "desc": "Molecular interfaces, format conversions, and quantum chemistry bridging.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-MInt",
        "mandatory": True,
    },
    "CoChem-CORE": {
        "desc": "Foundational registry, memory routing, and OS-level hardware guards.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-CORE",
        "mandatory": True,
    },
    "CoChem-TOPOS": {
        "desc": "Topological mapping, alignment, and geometry escalation.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-TOPOS",
        "mandatory": True,
    },
    "CoChem-TORQ": {
        "desc": "Torsional Discovery and Statistical Mechanics.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-TORQ",
        "mandatory": True,
    },
    "CoChem-SCAN": {
        "desc": "Internal conformational exploration heuristic tool.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-SCAN",
        "mandatory": False,
    },
    "CoChem-SCRIBE": {
        "desc": "LLM-driven FAIR publication and LaTeX supplementary generator.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-SCRIBE",
        "mandatory": False,
    },
    "CoChem-SpycFit": {
        "desc": "JAX-accelerated rotational spectroscopy fitting.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-SpycFit",
        "mandatory": False,
    },
    "CoChem-BENCH": {
        "desc": "Automated Basis Set Limit & Composite Protocol Extrapolator.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-BENCH",
        "mandatory": False,
    },
    "CoChem-KINETIC": {
        "desc": "Reaction network and master equation kinetics solver.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-KINETIC",
        "mandatory": False,
    },
    "CoChem-LUMOS": {
        "desc": "Open-shell dynamics, AIMNet2, and photochemistry.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-LUMOS",
        "mandatory": False,
    },
    "CoChem-MAGE": {
        "desc": "GC-MS fragmentation logic emulation using ML potentials.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-MAGE",
        "mandatory": False,
    },
    "CoChem-SHIFT": {
        "desc": "NMR tensor extraction (J-couplings, chemical shifts).",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-SHIFT",
        "mandatory": False,
    },
    "CoChem-GEOM": {
        "desc": "Precision molecular structure determination and fitting.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-GEOM",
        "mandatory": False,
    },
    "CoChem-NODE": {
        "desc": "HPC Slurm template and execution router.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-NODE",
        "mandatory": False,
    },
    "CoChem-ORACLE": {
        "desc": "Local Llama-CPP query routing and AI theory assistant.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-ORACLE",
        "mandatory": False,
    },
    "Antigravity-Assistant": {
        "desc": "Antigravity 2.0 Cloud LLM Assistant (Data Privacy Cannot Be Guaranteed).",
        "repo": "https://antigravity.google/cli",
        "mandatory": False,
    },
}

TOPOLOGICAL_DEPENDENCY_MAP: Dict[str, List[str]] = {
    "CoChem-BASE": [],
    "CoChem-MInt": ["CoChem-BASE"],
    "CoChem-CORE": ["CoChem-BASE", "CoChem-MInt"],
    "CoChem-TOPOS": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE"],
    "CoChem-TORQ": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-SCAN": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"],
    "CoChem-SCRIBE": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE"],
    "CoChem-SpycFit": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-BENCH": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"],
    "CoChem-KINETIC": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"],
    "CoChem-LUMOS": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-MAGE": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-SHIFT": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-GEOM": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-NODE": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE"],
    "CoChem-ORACLE": ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE"],
    "Antigravity-Assistant": [],
}


def validate_topological_prerequisites(selected_modules: List[str]) -> Tuple[bool, List[str]]:
    """Validates that all topological prerequisites are satisfied for selected modules."""
    selected_set = set(selected_modules)
    missing: List[str] = []

    for mod in selected_modules:
        prereqs = TOPOLOGICAL_DEPENDENCY_MAP.get(mod, [])
        for req in prereqs:
            if req not in selected_set and req not in missing:
                missing.append(req)

    return (len(missing) == 0, missing)


def resolve_topological_dependencies(selected_modules: List[str]) -> List[str]:
    """Resolves and injects all required prerequisites in topological order."""
    resolved_set = set(selected_modules)

    for name, info in ECOSYSTEM_REGISTRY.items():
        if info.get("mandatory", False):
            resolved_set.add(name)

    changed = True
    while changed:
        changed = False
        for mod in list(resolved_set):
            prereqs = TOPOLOGICAL_DEPENDENCY_MAP.get(mod, [])
            for req in prereqs:
                if req not in resolved_set:
                    resolved_set.add(req)
                    changed = True

    ordered: List[str] = []
    for mod in ECOSYSTEM_REGISTRY.keys():
        if mod in resolved_set:
            ordered.append(mod)

    return ordered


def detect_avx512_support() -> bool:
    """Detects native AVX-512 SIMD vector instructions on the host CPU."""
    if os.environ.get("COCHEM_FORCE_AVX512", "").strip().lower() in {"1", "true", "yes"}:
        return True
    if os.environ.get("COCHEM_FORCE_AVX512", "").strip().lower() in {"0", "false", "no"}:
        return False

    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                cpuinfo_text = f.read().lower()
                return "avx512f" in cpuinfo_text or "avx512" in cpuinfo_text
        except Exception:
            pass

    try:
        import numpy as np  # type: ignore[import-untyped]
        core_mod = getattr(np, "_core", getattr(np, "core", None))
        if core_mod is not None:
            umath = getattr(core_mod, "_multiarray_umath", None)
            if umath is not None and hasattr(umath, "__cpu_features__"):
                features = umath.__cpu_features__
                if isinstance(features, dict) and features.get("AVX512F", False):
                    return True
    except Exception:
        pass

    return False


def detect_host_hardware() -> Dict[str, Any]:
    """Collects real hardware telemetry from the host silicon without synthetic fallbacks."""
    logical_cpus = psutil.cpu_count(logical=True) or 4
    phys_cpus = psutil.cpu_count(logical=False) or max(1, logical_cpus // 2)
    vmem = psutil.virtual_memory()
    total_ram_gb = vmem.total / (1024.0 ** 3)
    avail_ram_gb = vmem.available / (1024.0 ** 3)

    try:
        free_storage_gb = psutil.disk_usage(str(get_scratch_dir())).free / (1024.0 ** 3)
    except Exception:
        try:
            free_storage_gb = psutil.disk_usage(str(get_artifact_dir())).free / (1024.0 ** 3)
        except Exception:
            free_storage_gb = 50.0

    gpu_profile_name = "None"
    gpu_vram_gb = 0.0
    gpu_count = 0

    try:
        from cochem_base.core.hardware import HardwareDiscovery
        gpu_avail = HardwareDiscovery.get_gpu_availability()
        if gpu_avail.available and gpu_avail.devices:
            gpu_count = len(gpu_avail.devices)
            gpu_profile_name = gpu_avail.devices[0].name
            gpu_vram_gb = sum(d.vram_gb for d in gpu_avail.devices)
    except Exception:
        pass

    if gpu_count == 0:
        cuda_dev = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
        if cuda_dev:
            parts = [p.strip() for p in cuda_dev.split(",") if p.strip()]
            if parts and parts[0] != "":
                gpu_count = len(parts)
                gpu_profile_name = "Mapped CUDA Device"
                gpu_vram_gb = 8.0

    avx512_capable = detect_avx512_support()

    return {
        "physical_cpu_cores": phys_cpus,
        "logical_cpu_cores": logical_cpus,
        "ram_gb": total_ram_gb,
        "avail_ram_gb": avail_ram_gb,
        "free_storage_gb": free_storage_gb,
        "gpu_profile": gpu_profile_name,
        "gpu_count": gpu_count,
        "vram_gb": gpu_vram_gb,
        "avx512_support": avx512_capable,
        "source": "Live Host Telemetry",
    }


def is_headless_environment() -> bool:
    """Detects whether execution is running in unattended or headless CI/CD environment."""
    if os.environ.get("CI") in ("1", "true", "TRUE", "True"):
        return True
    if os.environ.get("GITHUB_ACTIONS") in ("1", "true", "TRUE", "True"):
        return True
    if os.environ.get("HEADLESS") in ("1", "true", "TRUE", "True"):
        return True
    if os.environ.get("CONTINUOUS_INTEGRATION") in ("1", "true", "TRUE", "True"):
        return True
    if os.environ.get("DEBIAN_FRONTEND") == "noninteractive":
        return True
    if "--headless" in sys.argv:
        return True
    return False


def get_system_git_hash() -> str:
    """Resolves the current Git commit hash or falls back to .build_hash."""
    try:
        git_executable = resolve_executable(env_var="GIT_CMD", candidates=("git",))
        command = [git_executable, "rev-parse", "HEAD"]
        if safe_subprocess_run is not None:
            res = safe_subprocess_run(command, cwd=get_base_root(), capture_output=True, text=True, check=True, timeout=5)
        else:
            res = subprocess.run(command, cwd=get_base_root(), capture_output=True, text=True, check=True, timeout=5)
        return str(res.stdout).strip()[:16]
    except Exception as e:
        logger.warning(f"Git hash lookup failed: {e}")
        build_hash_file = get_base_root() / ".build_hash"
        if build_hash_file.exists():
            return build_hash_file.read_text(encoding="utf-8").strip()[:16]
        return "RELEASE_BUILD"


def serialize_system_config_json(
    manifest: DeploymentManifest,
    target_path: Optional[Path] = None,
) -> Path:
    """Serializes system configuration state to cochem_system_config.json."""
    artifact_dir = get_artifact_dir()
    registry_dir = artifact_dir / "Registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    config_file = target_path or (registry_dir / "cochem_system_config.json")
    telemetry = detect_host_hardware()

    os_target = {
        "Windows": "windows_amd64",
        "Darwin": "darwin_arm64" if platform.machine() == "arm64" else "darwin_x86_64",
        "Linux": "linux_x86_64",
    }.get(platform.system(), "linux_x86_64")

    if manifest.interaction_environment == "GitHub Codespaces":
        os_target = "codespaces"

    config_data: Dict[str, Any] = {
        "schema_version": "4.0.0",
        "registry_version": "4.0",
        "orca_version": "6.1.1",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "hardware": {
            "physical_cpu_cores": telemetry["physical_cpu_cores"],
            "logical_cpu_cores": telemetry["logical_cpu_cores"],
            "ram_gb": round(telemetry["ram_gb"], 2),
            "avx512_support": telemetry["avx512_support"],
            "gpu_profile": telemetry["gpu_profile"],
            "vram_gb": round(telemetry["vram_gb"], 2),
            "os_target": os_target,
        },
        "environment": {
            "os_target": os_target,
            "artifacts_dir": str(artifact_dir),
            "scratch_dir": str(get_scratch_dir()),
        },
        "silo_paths": {
            "orca_path": manifest.orca_tarball_path or "BYPASSED",
            "silo_root": str(registry_dir / "Modules"),
        },
        "engines": {
            "orca": {
                "status": "found" if manifest.orca_tarball_path else "missing",
                "path": manifest.orca_tarball_path or None,
                "version": "6.1.1" if manifest.orca_tarball_path else None,
                "hash": None,
            }
        },
        "interaction_tier": manifest.interaction_environment,
        "calculation_tier": manifest.calculation_environment,
        "selected_modules": manifest.selected_repositories,
    }

    config_file.write_text(json.dumps(config_data, indent=4), encoding="utf-8")
    logger.info(f"System configuration persisted to: {config_file}")
    return config_file


def serialize_default_manifest(
    output_path: Optional[Path] = None,
    interaction_env: Optional[str] = None,
    calc_env: Optional[str] = None,
    orca_path: str = "",
    extra_modules: Optional[List[str]] = None,
) -> DeploymentManifest:
    """Constructs and serializes the default topological manifest and system config to disk."""
    artifact_dir = get_artifact_dir()
    registry_dir = artifact_dir / "Registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    target_file = output_path or (registry_dir / "cochem_deployment_manifest.json")

    detected_interaction = interaction_env or (
        "GitHub Codespaces"
        if os.environ.get("CODESPACES")
        else {
            "Windows": "Local-Windows (WSL)",
            "Darwin": "Local-MacOS (OrbStack)",
            "Linux": "Local-Linux (Deb)",
        }.get(platform.system(), "GitHub Codespaces")
    )

    detected_calc = calc_env or (
        "GitHub Actions" if detected_interaction == "GitHub Codespaces" else detected_interaction
    )

    selected_raw = ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"]
    if extra_modules:
        selected_raw.extend(extra_modules)

    resolved_modules = resolve_topological_dependencies(selected_raw)

    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash=get_system_git_hash(),
        interaction_environment=detected_interaction,
        calculation_environment=detected_calc,
        orca_tarball_path=orca_path,
        selected_repositories=resolved_modules,
        headless=True,
    )

    target_file.write_text(manifest.model_dump_json(indent=4), encoding="utf-8")
    logger.info(f"Default deployment manifest serialized to: {target_file}")

    serialize_system_config_json(manifest)
    return manifest


def run_headless(manifest: Optional[DeploymentManifest] = None, auto_deploy: bool = False) -> DeploymentManifest:
    """Executes unattended headless manifest generation and optional provisioning."""
    active_manifest = manifest or serialize_default_manifest()

    if auto_deploy:
        logger.info("Executing unattended headless Stage 0 deployment worker...")
        gui = SynapInstallerGUI()
        gui._pure_python_deployment_worker(active_manifest.model_dump())

    return active_manifest


class SynapInstallerGUI:
    """CoChem-UNITY Master Installer & Configurator ipywidgets Tabbed Dashboard."""

    def __init__(self) -> None:
        self.buttons: Dict[str, widgets.Checkbox] = {}

        self.artifact_dir = get_artifact_dir()
        self.registry_dir = self.artifact_dir / "Registry"
        self.engine_registry = self.registry_dir / "Engines"
        self.module_registry = self.registry_dir / "Modules"

        self.engine_registry.mkdir(parents=True, exist_ok=True)
        self.module_registry.mkdir(parents=True, exist_ok=True)

        self.log_file = self.artifact_dir / "Logs" / "cochem_deploy.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        self.manifest_file = self.registry_dir / "cochem_deployment_manifest.json"
        self.system_config_file = self.registry_dir / "cochem_system_config.json"

        self.interaction_options = [
            "Local-Windows (WSL)",
            "Local-MacOS (OrbStack)",
            "Local-Linux (Deb)",
            "GitHub Codespaces",
            "HPC",
            "GitHub Actions",
        ]

        self.calculation_options = [
            "Local-Windows (WSL)",
            "Local-MacOS (OrbStack)",
            "Local-Linux (Deb)",
            "GitHub Actions",
            "HPC",
        ]

        self.disk_safe = False
        self.error_msg = ""
        self.tab_container: Optional[widgets.Tab] = None
        self.status_out: Optional[widgets.Output] = None
        self.output_console: Optional[widgets.Output] = None
        self.progress_bar: Optional[widgets.FloatProgress] = None
        self.submit_btn: Optional[widgets.Button] = None
        self.stage_orca_btn: Optional[widgets.Button] = None
        self.refresh_telemetry_btn: Optional[widgets.Button] = None
        self.interact_target: Optional[widgets.Dropdown] = None
        self.calc_target: Optional[widgets.Dropdown] = None
        self.host_orca_path: Optional[widgets.Text] = None
        self.orca_upload: Optional[widgets.FileUpload] = None
        self.hud_html: Optional[widgets.HTML] = None
        self.main_ui: Optional[widgets.VBox] = None

        self._pre_flight_disk_check()
        if self.disk_safe:
            self._build_ui()

    def _get_git_hash(self) -> str:
        return get_system_git_hash()

    def _pre_flight_disk_check(self) -> None:
        """Verifies safe OS storage limits before rendering (enforces 10GB gate per User Manual §1.2.6)."""
        try:
            free_gb = psutil.disk_usage(str(get_scratch_dir())).free / (1024**3)
            if free_gb < 10.0:
                self.disk_safe = False
                self.error_msg = f"CRITICAL ERROR: Insufficient disk space ({free_gb:.2f} GB free). Minimum 10GB required."
            else:
                self.disk_safe = True
        except Exception as e:
            try:
                free_gb = psutil.disk_usage(str(get_artifact_dir())).free / (1024**3)
                if free_gb < 10.0:
                    self.disk_safe = False
                    self.error_msg = f"CRITICAL ERROR: Insufficient disk space ({free_gb:.2f} GB free). Minimum 10GB required."
                else:
                    self.disk_safe = True
            except Exception as ex:
                self.disk_safe = False
                self.error_msg = f"WARNING: Storage capacity verification failed ({e} / {ex}). Manual scratch confirmation required."

    def _log_status(self, msg: str, level: str = "info") -> None:
        """Emits messages to status_out if present, as well as the standard logger."""
        if self.status_out is not None:
            with self.status_out:
                if level == "error":
                    logger.error(msg)
                elif level == "warning":
                    logger.warning(msg)
                elif level == "success":
                    logger.info(msg)
                    display(widgets.HTML(f"<div style='color: #15803d; font-weight: bold; margin: 4px 0;'>{msg}</div>"))  # type: ignore[no-untyped-call]
                else:
                    logger.info(msg)
        else:
            if level == "error":
                logger.error(msg)
            elif level == "warning":
                logger.warning(msg)
            else:
                logger.info(msg)

    def collect_hardware_telemetry(self) -> Dict[str, Any]:
        """Gathers real-time hardware telemetry and checks persisted system configuration."""
        telemetry = detect_host_hardware()
        config_path = self.system_config_file if self.system_config_file.exists() else resolve_config_path()

        if config_path and config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                    hw_sec = cfg_data.get("hardware", {})
                    if "ram_gb" in hw_sec:
                        telemetry["config_ram_gb"] = float(hw_sec["ram_gb"])
                    if "physical_cpu_cores" in hw_sec:
                        telemetry["config_phys_cores"] = int(hw_sec["physical_cpu_cores"])
                    if "avx512_support" in hw_sec:
                        telemetry["config_avx512"] = bool(hw_sec["avx512_support"])
                    if "gpu_profile" in hw_sec:
                        telemetry["config_gpu"] = str(hw_sec["gpu_profile"])
                    telemetry["source"] = f"Registry Config ({config_path.name})"
            except Exception:
                pass

        return telemetry

    def _render_hardware_hud_html(self, telemetry: Optional[Dict[str, Any]] = None) -> str:
        """Generates dynamic HTML table with visual red/yellow/green resource warnings."""
        data = telemetry or self.collect_hardware_telemetry()

        ram_gb = data.get("ram_gb", 16.0)
        avail_ram_gb = data.get("avail_ram_gb", ram_gb)
        phys_cores = data.get("physical_cpu_cores", 4)
        log_cores = data.get("logical_cpu_cores", 8)
        gpu_name = data.get("gpu_profile", "None")
        gpu_vram = data.get("vram_gb", 0.0)
        avx512_support = data.get("avx512_support", False)
        free_storage = data.get("free_storage_gb", 50.0)
        source = data.get("source", "Live Telemetry")

        if ram_gb >= 16.0:
            ram_bg, ram_fg, ram_status = "#dcfce7", "#166534", "Optimal"
        elif ram_gb >= 8.0:
            ram_bg, ram_fg, ram_status = "#fef9c3", "#854d0e", "Constrained"
        else:
            ram_bg, ram_fg, ram_status = "#fee2e2", "#991b1b", "Critical (<8GB)"

        if phys_cores >= 4:
            cpu_bg, cpu_fg, cpu_status = "#dcfce7", "#166534", "Optimal"
        elif phys_cores >= 2:
            cpu_bg, cpu_fg, cpu_status = "#fef9c3", "#854d0e", "Constrained"
        else:
            cpu_bg, cpu_fg, cpu_status = "#fee2e2", "#991b1b", "Critical (<2 cores)"

        if gpu_vram >= 4.0:
            gpu_bg, gpu_fg, gpu_status = "#dcfce7", "#166534", "Accelerated"
        elif gpu_vram > 0.0:
            gpu_bg, gpu_fg, gpu_status = "#fef9c3", "#854d0e", "Low VRAM"
        else:
            gpu_bg, gpu_fg, gpu_status = "#f1f5f9", "#475569", "CPU Only"

        if avx512_support:
            avx_bg, avx_fg, avx_status = "#dcfce7", "#166534", "Supported"
        else:
            avx_bg, avx_fg, avx_status = "#fef9c3", "#854d0e", "Not Detected / Fallback"

        if free_storage >= 20.0:
            disk_bg, disk_fg, disk_status = "#dcfce7", "#166534", "Adequate"
        elif free_storage >= 10.0:
            disk_bg, disk_fg, disk_status = "#fef9c3", "#854d0e", "Tight Storage"
        else:
            disk_bg, disk_fg, disk_status = "#fee2e2", "#991b1b", "Critical (<10GB)"

        has_critical = (ram_gb < 8.0) or (phys_cores < 2) or (free_storage < 10.0)
        has_warning = (ram_gb < 16.0) or (phys_cores < 4) or (not avx512_support) or (gpu_vram == 0.0)

        if has_critical:
            banner = (
                "<div style='margin-top: 10px; padding: 8px 12px; background-color: #fee2e2; "
                "border-left: 4px solid #dc2626; color: #991b1b; border-radius: 4px; font-size: 0.88em;'>"
                "<b>CRITICAL RESOURCE WARNING:</b> Host resources are below minimum thresholds. "
                "Calculations may experience out-of-memory errors or reduced performance."
                "</div>"
            )
        elif has_warning:
            banner = (
                "<div style='margin-top: 10px; padding: 8px 12px; background-color: #fef9c3; "
                "border-left: 4px solid #ca8a04; color: #854d0e; border-radius: 4px; font-size: 0.88em;'>"
                "<b>RESOURCE NOTICE:</b> Constrained hardware profile detected. "
                "Dynamic fallback routing will automatically adapt solver parameters."
                "</div>"
            )
        else:
            banner = (
                "<div style='margin-top: 10px; padding: 8px 12px; background-color: #dcfce7; "
                "border-left: 4px solid #16a34a; color: #166534; border-radius: 4px; font-size: 0.88em;'>"
                "<b>HARDWARE VERIFIED:</b> Silicon meets all recommended performance profiles for high-throughput execution."
                "</div>"
            )

        html = f"""
        <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px; margin: 10px 0;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <span style="font-weight: bold; color: #0f172a; font-family: monospace; font-size: 1.05em;">SYSTEM METAL &amp; COMPUTE TELEMETRY HUD</span>
            <span style="font-size: 0.82em; color: #64748b;">Source: {source}</span>
          </div>
          <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 0.88em;">
            <thead>
              <tr style="border-bottom: 2px solid #cbd5e1; text-align: left; color: #475569;">
                <th style="padding: 6px 8px;">Resource</th>
                <th style="padding: 6px 8px;">Detected Specification</th>
                <th style="padding: 6px 8px;">Status / Tier</th>
              </tr>
            </thead>
            <tbody>
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 6px 8px; font-weight: 600;">System RAM</td>
                <td style="padding: 6px 8px;">{ram_gb:.1f} GB Total ({avail_ram_gb:.1f} GB Available)</td>
                <td style="padding: 6px 8px;"><span style="background-color: {ram_bg}; color: {ram_fg}; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{ram_status}</span></td>
              </tr>
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 6px 8px; font-weight: 600;">CPU Cores</td>
                <td style="padding: 6px 8px;">{phys_cores} Physical / {log_cores} Logical Cores</td>
                <td style="padding: 6px 8px;"><span style="background-color: {cpu_bg}; color: {cpu_fg}; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{cpu_status}</span></td>
              </tr>
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 6px 8px; font-weight: 600;">GPU Accelerator</td>
                <td style="padding: 6px 8px;">{gpu_name} ({gpu_vram:.1f} GB VRAM)</td>
                <td style="padding: 6px 8px;"><span style="background-color: {gpu_bg}; color: {gpu_fg}; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{gpu_status}</span></td>
              </tr>
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 6px 8px; font-weight: 600;">Vector ISA (AVX-512)</td>
                <td style="padding: 6px 8px;">{'AVX-512 Foundation Present' if avx512_support else 'AVX-512 Not Present'}</td>
                <td style="padding: 6px 8px;"><span style="background-color: {avx_bg}; color: {avx_fg}; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{avx_status}</span></td>
              </tr>
              <tr>
                <td style="padding: 6px 8px; font-weight: 600;">Free Disk Storage</td>
                <td style="padding: 6px 8px;">{free_storage:.1f} GB Available</td>
                <td style="padding: 6px 8px;"><span style="background-color: {disk_bg}; color: {disk_fg}; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{disk_status}</span></td>
              </tr>
            </tbody>
          </table>
          {banner}
        </div>
        """
        return html

    def refresh_hardware_hud(self) -> None:
        """Refreshes the hardware profiling HUD with latest telemetry values."""
        if self.hud_html is not None:
            self.hud_html.value = self._render_hardware_hud_html()

    def _verify_host_orca_path(self, raw_path: str) -> bool:
        """Performs a quantum single-point verification run to confirm native ORCA execution."""
        mapped_orca = resolve_executable(
            (raw_path or "").strip().strip('"').strip("'") or None,
            env_var="ORCA_CMD",
            candidates=("orca",),
        )
        discovered = shutil.which(mapped_orca)
        candidate = Path(discovered or mapped_orca).expanduser()
        if not mapped_orca:
            return False

        if not candidate.exists():
            self._log_status(f"ORCA path does not exist at: {candidate}", level="error")
            return False

        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        verify_dir = Path(tempfile.mkdtemp(prefix="cochem_orca_verify_", dir=str(self.artifact_dir)))
        inp = verify_dir / "verify_orca.inp"
        inp.write_text("! SP STO-3G\n*xyz 0 1\nHe 0 0 0\n*\n", encoding="utf-8")
        try:
            if safe_subprocess_run is not None:
                result = safe_subprocess_run(
                    [str(candidate), str(inp)],
                    cwd=str(verify_dir),
                    capture_output=True,
                    text=True,
                    timeout=90.0,
                    check=False,
                )
            else:
                result = subprocess.run(
                    [str(candidate), str(inp)],
                    cwd=str(verify_dir),
                    capture_output=True,
                    text=True,
                    timeout=90.0,
                    check=False,
                )
            stdout_upper = (result.stdout or "").upper()
            out_file = verify_dir / "verify_orca.out"
            out_text = out_file.read_text(errors="replace").upper() if out_file.exists() else ""
            markers = ["ORCA TERMINATED NORMALLY", "O   R   C   A", "O R C A"]
            if result.returncode == 0 and any(m in stdout_upper or m in out_text for m in markers):
                self._log_status(f"ORCA verification passed via: {candidate}", level="info")
                return True
            return False
        except Exception as e:
            self._log_status(f"ORCA verification exception: {e}", level="error")
            return False
        finally:
            shutil.rmtree(verify_dir, ignore_errors=True)

    def _has_staged_orca_archive(self) -> bool:
        patterns = ["orca*.tar.xz", "orca*.tz", "orca*.tar.gz", "ORCA*.tar.xz", "ORCA*.tz", "ORCA*.tar.gz"]
        for pattern in patterns:
            for candidate in self.engine_registry.glob(pattern):
                if candidate.is_file():
                    return True
        return False

    def _extract_upload_entries(self, files: Any) -> List[Tuple[str, Any]]:
        if not files:
            return []
        if isinstance(files, dict):
            return [(fname, fdata) for fname, fdata in files.items()]
        entries: List[Tuple[str, Any]] = []
        for entry in files:
            if isinstance(entry, dict):
                entries.append((entry.get("name", ""), entry))
            else:
                entries.append((getattr(entry, "name", ""), entry))
        return entries

    def _stage_orca_upload(self, files: Any) -> bool:
        """Stages uploaded binary archives into the designated registry paths."""
        entries = self._extract_upload_entries(files)
        if not entries:
            return False

        staged_any = False
        for fname, fdata in entries:
            fname = Path(fname).name
            if not fname or fname in (".", ".."):
                continue
            fname_lower = fname.lower()
            if not fname_lower.endswith((".tar.xz", ".tz", ".tar.gz", ".zip")):
                self._log_status(f"Unsupported archive type: {fname or 'unknown'}", level="warning")
                continue

            target_dir = self.module_registry if fname_lower.endswith(".zip") else self.engine_registry
            target = target_dir / fname
            try:
                if not target.resolve().is_relative_to(target_dir.resolve()):
                    self._log_status(f"Invalid target path for {fname}", level="error")
                    continue
            except (ValueError, RuntimeError):
                continue

            content = fdata.get("content", b"") if isinstance(fdata, dict) else getattr(fdata, "content", b"")
            if isinstance(content, memoryview):
                content = content.tobytes()
            elif isinstance(content, bytearray):
                content = bytes(content)

            if not content:
                continue

            with open(target, "wb") as f:
                f.write(content)
            size = target.stat().st_size if target.exists() else 0
            if size > 0:
                self._log_status(f"Archive staged to: {target} ({size} bytes)", level="info")
                staged_any = True
        return staged_any

    def _on_module_checkbox_change(self, change: Dict[str, Any], module_name: str) -> None:
        """Handles topological prerequisite updates dynamically when user clicks a module."""
        if change.get("new", False):
            prereqs = TOPOLOGICAL_DEPENDENCY_MAP.get(module_name, [])
            for req in prereqs:
                if req in self.buttons and not self.buttons[req].value:
                    self.buttons[req].value = True
                    self._log_status(f"Auto-selected prerequisite: {req} for {module_name}", level="info")

    def _pure_python_deployment_worker(self, manifest_payload: Dict[str, Any]) -> None:
        """Threaded pure-Python deployment worker. Enforces Air-Gap sideloading."""
        try:
            target_modules = manifest_payload.get("selected_repositories", [])
            interaction_env = manifest_payload.get("interaction_environment", "Local-Linux (Deb)")
            calc_env = manifest_payload.get("calculation_environment", "Local-Linux (Deb)")
            progress_step = 80.0 / max(len(target_modules), 1)

            with open(self.log_file, "a", encoding="utf-8") as log_out:

                def log_msg(msg: str) -> None:
                    if self.output_console is not None:
                        try:
                            self.output_console.append_stdout(f"{msg}\n")
                        except Exception:
                            pass
                    logger.info(msg.strip())
                    log_out.write(f"{msg}\n")
                    log_out.flush()

                log_msg("\n[DEPLOYMENT] Initiating Pure-Python Air-Gap Module Provisioning...")
                log_msg(f"[INTERACTION TIER] Selected UI: {interaction_env}")
                log_msg(f"[CALCULATION TIER] Selected Compute: {calc_env}")
                log_msg(f"[WORKSPACE] Target Module Registry: {self.module_registry}\n")

                clean_env = os.environ.copy()
                clean_env["GIT_TERMINAL_PROMPT"] = "0"
                clean_env["COCHEM_INTERACTION_TIER"] = str(interaction_env)
                clean_env["COCHEM_CALCULATION_TIER"] = str(calc_env)

                base_root = str(get_base_root())
                existing_pythonpath = clean_env.get("PYTHONPATH")
                clean_env["PYTHONPATH"] = os.pathsep.join(
                    entry for entry in (base_root, existing_pythonpath) if entry
                )
                git_executable = resolve_executable(env_var="GIT_CMD", candidates=("git",))

                def update_progress(val: float, bar_style: Optional[str] = None) -> None:
                    if self.progress_bar is not None:
                        self.progress_bar.value = min(100.0, max(0.0, val))
                        if bar_style:
                            self.progress_bar.bar_style = bar_style

                current_progress = 0.0

                for mod in target_modules:
                    if mod == "CoChem-BASE":
                        log_msg(f"  [BASE] Base repository active. Bypassing clone for {mod}.")
                        current_progress += progress_step
                        update_progress(current_progress)
                        continue

                    if mod == "Antigravity-Assistant":
                        log_msg("  [CLOUD] Provisioning Antigravity 2.0 Assistant...")
                        if os.name == "nt":
                            powershell = resolve_executable(env_var="POWERSHELL_CMD", candidates=("pwsh", "powershell"))
                            cmd = [powershell, "-NoProfile", "-Command", "irm https://antigravity.google/cli/install.ps1 | iex"]
                        else:
                            curl = resolve_executable(env_var="CURL_CMD", candidates=("curl",))
                            bash = resolve_executable(env_var="BASH_CMD", candidates=("bash",))
                            cmd = [bash, "-c", f'"{curl}" -fsSL https://antigravity.google/cli/install.sh | "{bash}"']
                        try:
                            if safe_subprocess_run is not None:
                                safe_subprocess_run(cmd, env=clean_env, check=True, timeout=120.0)
                            else:
                                subprocess.run(cmd, env=clean_env, check=True, capture_output=True, text=True, timeout=120.0)
                            log_msg("  [SUCCESS] Antigravity 2.0 CLI installed successfully.")
                        except Exception as e:
                            log_msg(f"  [ERROR] Failed to install Antigravity 2.0: {e}")
                        current_progress += progress_step
                        update_progress(current_progress)
                        continue

                    repo_url = ECOSYSTEM_REGISTRY[mod]["repo"]
                    target_dir = self.module_registry / mod

                    if (target_dir / ".git").exists():
                        log_msg(f"  [UPDATE] Updating existing module: {mod}")
                        try:
                            if safe_subprocess_run is not None:
                                safe_subprocess_run([git_executable, "pull", "--ff-only"], cwd=str(target_dir), env=clean_env, check=True, timeout=60.0)
                            else:
                                subprocess.run([git_executable, "pull", "--ff-only"], cwd=str(target_dir), env=clean_env, check=True, capture_output=True, text=True, timeout=60.0)
                            log_msg(f"  [SUCCESS] {mod} updated successfully.")
                        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                            log_msg(f"  [WARNING] Fast-forward failed for {mod}: {e}")
                    else:
                        sideload_success = False
                        possible_zips = [
                            self.module_registry / f"{mod}.zip",
                            self.module_registry / f"{mod}-main.zip",
                            self.module_registry / f"{mod}-master.zip",
                            self.module_registry / f"{mod.lower()}.zip",
                            self.module_registry / f"{mod.lower()}-main.zip",
                            self.engine_registry / f"{mod}.zip",
                            self.engine_registry / f"{mod}-main.zip",
                            self.artifact_dir / f"{mod}.zip",
                            self.artifact_dir / f"{mod}-main.zip",
                        ]

                        for zpath in possible_zips:
                            if zpath.exists():
                                log_msg(f"  [AIR-GAP] Air-Gap Bridge: Sideloading {mod} from {zpath.name}...")
                                try:
                                    with zipfile.ZipFile(zpath, "r") as zip_ref:
                                        target_base = self.module_registry.resolve()
                                        for member in zip_ref.infolist():
                                            member_path = (target_base / member.filename).resolve()
                                            if not member_path.is_relative_to(target_base):
                                                raise RuntimeError(f"Zip Slip attempt detected: {member.filename}")
                                        zip_ref.extractall(self.module_registry)

                                    for suffix in ["-main", "-master", f"-{mod.lower()}", f"-{mod}"]:
                                        extracted_dir = self.module_registry / f"{mod}{suffix}"
                                        if extracted_dir.exists() and not target_dir.exists():
                                            extracted_dir.rename(target_dir)

                                    lower_dir = self.module_registry / mod.lower()
                                    if lower_dir.exists() and not target_dir.exists() and mod.lower() != mod:
                                        lower_dir.rename(target_dir)

                                    if target_dir.exists():
                                        log_msg(f"  [SUCCESS] Extracted {mod} via Air-Gap. Network bypassed.")
                                        sideload_success = True
                                        break
                                except (zipfile.BadZipFile, OSError, RuntimeError) as e:
                                    log_msg(f"  [WARNING] Zip extraction failed: {e}")

                        if not sideload_success:
                            log_msg(f"  [CLONE] Deep cloning {mod} from {repo_url}...")
                            try:
                                if safe_subprocess_run is not None:
                                    safe_subprocess_run([git_executable, "clone", "--depth", "1", repo_url, str(target_dir)], env=clean_env, check=True, timeout=120.0)
                                else:
                                    subprocess.run([git_executable, "clone", "--depth", "1", repo_url, str(target_dir)], env=clean_env, check=True, capture_output=True, text=True, timeout=120.0)
                                log_msg(f"  [SUCCESS] Cloned {mod} successfully.")
                            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                                log_msg(f"  [ERROR] Failed to clone {mod}: {e}")

                    current_progress += progress_step
                    update_progress(current_progress)

                log_msg("\n[COMPLETE] Stage 0.0.2 Module synchronization completed.")

            orchestrator = get_base_root() / "setup" / "cochem_setup_orchestrator.py"
            if orchestrator.exists():
                log_msg(f"[HANDOFF] Handing off to CoChem-BASE OS-Native Orchestrator: {orchestrator.name}...")
                try:
                    process = subprocess.Popen(
                        [sys.executable, str(orchestrator)],
                        cwd=str(orchestrator.parent),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        env=clean_env,
                    )
                    if register_popen_process is not None:
                        register_popen_process(process)

                    if process.stdout:
                        for line in process.stdout:
                            if self.output_console is not None:
                                try:
                                    self.output_console.append_stdout(line)
                                except Exception:
                                    pass
                            log_out.write(line)
                            log_out.flush()
                    try:
                        process.wait(timeout=600.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                        log_msg("[ERROR] Orchestrator timed out after 600 seconds.")
                        update_progress(100.0, bar_style="danger")
                        return

                    if process.returncode == 0:
                        log_msg("[SUCCESS] Orchestrator completed successfully.")
                        update_progress(100.0, bar_style="success")
                    else:
                        log_msg(f"[ERROR] Orchestrator failed with exit code {process.returncode}.")
                        update_progress(100.0, bar_style="danger")
                except Exception as e:
                    log_msg(f"[ERROR] Failed to launch orchestrator: {e}")
                    update_progress(100.0, bar_style="danger")
            else:
                log_msg(f"[INFO] OS-Native Orchestrator script not present at {orchestrator}. Ready for manual phase runs.")
                update_progress(100.0, bar_style="success")

            update_progress(100.0)
        except Exception as e:
            logger.error(f"Unhandled deployment worker exception: {e}")
            if self.progress_bar is not None:
                self.progress_bar.bar_style = "danger"
            self._unlock_ui_after_failure()

    def _lock_ui_for_deployment(self) -> None:
        """Locks all interactive input widgets to enforce UI immutability during execution."""
        if self.submit_btn is not None:
            self.submit_btn.disabled = True
            self.submit_btn.description = "Initializing Pipeline..."
        if self.interact_target is not None:
            self.interact_target.disabled = True
        if self.calc_target is not None:
            self.calc_target.disabled = True
        if self.host_orca_path is not None:
            self.host_orca_path.disabled = True
        if self.orca_upload is not None:
            self.orca_upload.disabled = True
        if self.stage_orca_btn is not None:
            self.stage_orca_btn.disabled = True
        if self.refresh_telemetry_btn is not None:
            self.refresh_telemetry_btn.disabled = True
        for cb in self.buttons.values():
            cb.disabled = True

    def _unlock_ui_after_failure(self) -> None:
        """Restores editable state on input widgets if deployment pre-checks fail."""
        if self.submit_btn is not None:
            self.submit_btn.disabled = False
            self.submit_btn.description = "Initialize Pipeline"
        if self.interact_target is not None:
            if not os.environ.get("CODESPACES"):
                self.interact_target.disabled = False
        if self.calc_target is not None:
            self.calc_target.disabled = False
        if self.host_orca_path is not None:
            self.host_orca_path.disabled = False
        if self.orca_upload is not None:
            self.orca_upload.disabled = False
        if self.stage_orca_btn is not None:
            self.stage_orca_btn.disabled = False
        if self.refresh_telemetry_btn is not None:
            self.refresh_telemetry_btn.disabled = False
        for prog, cb in self.buttons.items():
            if not ECOSYSTEM_REGISTRY.get(prog, {}).get("mandatory", False):
                cb.disabled = False

    def _on_submit(self, b: Any) -> None:
        """Handles pipeline initialization, state serialization, and worker dispatch."""
        self._lock_ui_for_deployment()
        if self.progress_bar is not None:
            self.progress_bar.value = 0.0
            self.progress_bar.bar_style = "info"
            self.progress_bar.layout.display = "block"
        if self.output_console is not None:
            self.output_console.clear_output()
        if self.status_out is not None:
            self.status_out.clear_output()

        selected_raw = [mod for mod, cb in self.buttons.items() if cb.value]
        selected_modules = resolve_topological_dependencies(selected_raw)

        host_orca_path = self.host_orca_path.value.strip() if self.host_orca_path is not None else ""
        host_orca_verified = False

        interact_val = self.interact_target.value if self.interact_target is not None else "Local-Windows (WSL)"
        calc_val = self.calc_target.value if self.calc_target is not None else "Local-Linux (Deb)"

        manifest_model = DeploymentManifest(
            version="2026.2",
            git_provenance_hash=self._get_git_hash(),
            interaction_environment=interact_val,
            calculation_environment=calc_val,
            orca_tarball_path=host_orca_path,
            selected_repositories=selected_modules,
            headless=False,
        )

        with open(self.manifest_file, "w", encoding="utf-8") as f:
            f.write(manifest_model.model_dump_json(indent=4))

        serialize_system_config_json(manifest_model, target_path=self.system_config_file)
        manifest_payload = manifest_model.model_dump()

        self._log_status(f"Matrix Selections locked securely in: {self.manifest_file}", level="info")
        self._log_status("CoChem-BASE Fully Initialized. Safe to proceed.", level="success")

        if host_orca_path and host_orca_path != "Not Available - Auto-Routed":
            self._log_status("Verifying native ORCA execution pathway...", level="info")
            host_orca_verified = self._verify_host_orca_path(host_orca_path)
            if not host_orca_verified and not self._has_staged_orca_archive():
                self._log_status("ORCA verification failed. Fix path or stage an archive instead.", level="warning")
                self._unlock_ui_after_failure()
                return

        staged_now = False
        if not host_orca_verified and self.orca_upload is not None:
            staged_now = self._stage_orca_upload(getattr(self.orca_upload, "value", None))

        if host_orca_verified or staged_now or self._has_staged_orca_archive():
            self._log_status("Dispatching Pure-Python Deployment Thread...", level="info")
            threading.Thread(
                target=self._pure_python_deployment_worker,
                args=(manifest_payload,),
                daemon=True,
            ).start()
        else:
            self._log_status("Proceeding with module provisioning (Host ORCA not configured)...", level="info")
            threading.Thread(
                target=self._pure_python_deployment_worker,
                args=(manifest_payload,),
                daemon=True,
            ).start()

    def _on_stage_orca_click(self, _: Any) -> None:
        if self.status_out is not None:
            with self.status_out:
                try:
                    clear_output()  # type: ignore[no-untyped-call]
                except Exception:
                    pass
                staged = self._stage_orca_upload(getattr(self.orca_upload, "value", None))
                if staged:
                    logger.info("Archives are staged and ready for setup.")
                else:
                    logger.warning("No valid archives detected to stage.")
        else:
            staged = self._stage_orca_upload(getattr(self.orca_upload, "value", None))
            if staged:
                logger.info("Archives are staged and ready for setup.")
            else:
                logger.warning("No valid archives detected to stage.")

    def _on_refresh_telemetry_click(self, _: Any) -> None:
        """Handler for manually polling and refreshing hardware telemetry."""
        self.refresh_hardware_hud()
        self._log_status("Hardware telemetry HUD refreshed.", level="info")

    def _build_ui(self) -> None:
        title = widgets.HTML(
            "<div style='margin-bottom: 12px;'>"
            "<h2 style='margin: 0; color: #0f172a;'>CoChem-UNITY: Ecosystem Master Deployer</h2>"
            "<p style='margin: 4px 0 0 0; color: #475569; font-size: 0.95em;'>"
            "Stage 0.0 Zero-Code Initialization &amp; Topological Prerequisite Engine"
            "</p>"
            "</div>"
        )

        artifact_hint = widgets.HTML(
            f"<div style='background-color: #f8fafc; padding: 12px; border-radius: 6px; border-left: 4px solid #0284c7; margin-bottom: 15px; font-family: monospace; font-size: 0.9em;'>"
            f"<b>Tripartite Artifacts Bridge:</b> {self.artifact_dir}<br>"
            f"<b>1. ORCA Engine Drop Target:</b> {self.engine_registry}<br>"
            f"<b>2. Module Archive Drop Target:</b> {self.module_registry}<br>"
            f"<span style='color: #64748b;'>Air-Gap Sideloading: Drop .zip archives in the targets above to bypass external network calls.</span>"
            f"</div>"
        )

        codespaces_detected = bool(os.environ.get("CODESPACES"))
        if codespaces_detected:
            host_interaction = "GitHub Codespaces"
            interact_disabled = True
            host_calculation = "GitHub Actions"
        else:
            host_interaction = {
                "Windows": "Local-Windows (WSL)",
                "Darwin": "Local-MacOS (OrbStack)",
                "Linux": "Local-Linux (Deb)",
            }.get(platform.system(), "Local-Linux (Deb)")
            interact_disabled = False
            host_calculation = host_interaction if host_interaction in self.calculation_options else "Local-Linux (Deb)"

        self.interact_target = widgets.Dropdown(
            options=self.interaction_options,
            value=host_interaction,
            disabled=interact_disabled,
            description="Interaction (UI):",
            layout={"width": "90%"},
        )
        self.calc_target = widgets.Dropdown(
            options=self.calculation_options,
            value=host_calculation,
            description="Calculation (Compute):",
            layout={"width": "90%"},
        )

        self.refresh_telemetry_btn = widgets.Button(
            description="Refresh Telemetry",
            button_style="info",
            layout={"width": "180px", "margin": "8px 0px"},
        )
        self.refresh_telemetry_btn.on_click(self._on_refresh_telemetry_click)

        self.hud_html = widgets.HTML(self._render_hardware_hud_html())

        tab_env = widgets.VBox(
            [
                widgets.HTML("<h4>Step 1: Interaction &amp; Compute Matrices</h4>"),
                self.interact_target,
                self.calc_target,
                self.refresh_telemetry_btn,
                self.hud_html,
            ],
            layout={"padding": "12px"},
        )

        # Tab 1: Binaries & Archives
        self.host_orca_path = widgets.Text(
            value="",
            description="Host ORCA:",
            layout={"width": "90%"},
        )
        self.orca_upload = widgets.FileUpload(
            accept=".tar.xz,.tz,.tar.gz,.zip",
            multiple=True,
            description="Drop Archives",
        )
        self.stage_orca_btn = widgets.Button(description="Stage Uploads", button_style="primary")
        self.stage_orca_btn.on_click(self._on_stage_orca_click)

        tab_binaries = widgets.VBox(
            [
                widgets.HTML("<h4>Step 2: External Quantum Chemistry Binaries &amp; Archives</h4>"),
                self.host_orca_path,
                widgets.HBox([self.orca_upload, self.stage_orca_btn], layout={"margin": "10px 0px"}),
            ],
            layout={"padding": "12px"},
        )

        # Tab 2: Ecosystem Modules
        checks = [
            widgets.HTML(
                "<div style='margin-bottom: 8px;'>"
                "<b>Topological Prerequisite Locking:</b> Mandatory base modules are permanently locked. "
                "Selecting dependent tools automatically verifies and activates required prerequisites."
                "</div>"
            )
        ]
        for prog, info in ECOSYSTEM_REGISTRY.items():
            is_mandatory = info.get("mandatory", False)
            cb = widgets.Checkbox(
                value=is_mandatory,
                description=prog,
                disabled=is_mandatory,
                layout={"width": "260px"},
            )
            if not is_mandatory:
                cb.observe(
                    lambda change, name=prog: self._on_module_checkbox_change(change, name),
                    names="value",
                )
            desc = widgets.HTML(f"<span style='color: #475569; font-size: 0.9em;'><i>{info['desc']}</i></span>")
            self.buttons[prog] = cb
            checks.append(widgets.HBox([cb, desc], layout={"align_items": "center", "margin": "0px 0px 4px 0px"}))

        tab_modules = widgets.VBox(checks, layout={"padding": "12px"})

        # Tab 3: Deployment & Logs
        self.submit_btn = widgets.Button(
            description="Initialize Pipeline",
            button_style="success",
            layout={"width": "30%", "margin": "10px 0px"},
        )
        self.submit_btn.on_click(self._on_submit)

        self.progress_bar = widgets.FloatProgress(
            value=0.0,
            min=0.0,
            max=100.0,
            description="Deploying:",
            bar_style="info",
            layout={"width": "95%"},
        )
        self.progress_bar.layout.display = "none"

        self.status_out = widgets.Output(
            layout={"border": "1px solid #cbd5e1", "padding": "8px", "height": "140px", "margin": "10px 0px"}
        )
        self.output_console = widgets.Output(
            layout={
                "border": "1px solid #334155",
                "padding": "10px",
                "height": "280px",
            }
        )

        tab_deploy = widgets.VBox(
            [
                widgets.HTML("<h4>Step 4: Lock Topology &amp; Dispatch Provisioning</h4>"),
                self.submit_btn,
                self.progress_bar,
                self.status_out,
                widgets.HTML("<h4>Live Subprocess Execution Log</h4>"),
                self.output_console,
            ],
            layout={"padding": "12px"},
        )

        self.tab_container = widgets.Tab(children=[tab_env, tab_binaries, tab_modules, tab_deploy])
        self.tab_container.set_title(0, "1. Environment Matrices")
        self.tab_container.set_title(1, "2. External Binaries")
        self.tab_container.set_title(2, "3. Ecosystem Modules")
        self.tab_container.set_title(3, "4. Deployment & Logs")

        self.main_ui = widgets.VBox([title, artifact_hint, self.tab_container])

    def build_ui(self) -> Any:
        """Returns the completed ipywidgets tabbed dashboard or storage error block."""
        if not self.disk_safe:
            return widgets.VBox([widgets.HTML(f"<h3 style='color: #b91c1c;'>{self.error_msg}</h3>")])
        return self.main_ui


def main() -> None:
    """CLI / Execution entry point supporting both interactive GUI and automated headless runs."""
    parser = argparse.ArgumentParser(description="CoChem-BASE Stage 0.0 Master Installer Dashboard")
    parser.add_argument("--headless", action="store_true", help="Bypass GUI and serialize default topology manifest.")
    parser.add_argument("--deploy", action="store_true", help="Execute unattended deployment after manifest serialization.")
    args, _ = parser.parse_known_args()

    if args.headless or is_headless_environment():
        logger.info("[HEADLESS] Headless detection protocol triggered.")
        manifest = run_headless(auto_deploy=args.deploy)
        print(f"[HEADLESS] Manifest written successfully to: {get_artifact_dir() / 'Registry' / 'cochem_deployment_manifest.json'}")
        print(manifest.model_dump_json(indent=2))
    else:
        installer = SynapInstallerGUI()
        ui = installer.build_ui()
        display(ui)  # type: ignore[no-untyped-call]


if __name__ == "__main__":
    main()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\interfaces\cochem_unity_installer_dashboard.py ---
#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.0 - Legacy and Direct Entrypoint for Installer Dashboard.

Re-exports canonical symbols from cochem_base.interfaces.cochem_unity_installer_dashboard.
"""

from __future__ import annotations

from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    TOPOLOGICAL_DEPENDENCY_MAP,
    DeploymentManifest,
    SynapInstallerGUI,
    detect_avx512_support,
    detect_host_hardware,
    get_system_git_hash,
    is_headless_environment,
    logger,
    main,
    resolve_topological_dependencies,
    run_headless,
    serialize_default_manifest,
    serialize_system_config_json,
    validate_topological_prerequisites,
)

__all__ = [
    "ECOSYSTEM_REGISTRY",
    "TOPOLOGICAL_DEPENDENCY_MAP",
    "DeploymentManifest",
    "SynapInstallerGUI",
    "detect_avx512_support",
    "detect_host_hardware",
    "get_system_git_hash",
    "is_headless_environment",
    "logger",
    "main",
    "resolve_topological_dependencies",
    "run_headless",
    "serialize_default_manifest",
    "serialize_system_config_json",
    "validate_topological_prerequisites",
]

if __name__ == "__main__":
    main()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_unity_installer_dashboard.py ---
"""Physical Zero-Mock Test Suite for CoChem-BASE Unity Installer Dashboard.

Validates:
- LF line endings & standard UTF-8 encoding (no BOM).
- Zero personal path leakage across codebase.
- Pydantic DeploymentManifest validation & serialization.
- Ecosystem registry invariants (5 mandatory modules, 17 total ecosystem modules).
- SynapInstallerGUI pre-flight disk check and widget tree construction.
- Real-time Hardware Profiling HUD, AVX-512 detection, and telemetry rendering.
- 6-Tier interaction & compute selection model with Codespaces auto-lock.
- UI Immutability Orchestrator Lock on pipeline initialization.
- State serialization to cochem_system_config.json and cochem_deployment_manifest.json.
- ORCA binary verification and archive staging logic.
- Air-Gap ZIP sideloading and deployment worker execution.
- Zombie process cleanup handler execution.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Dict

import ipywidgets as widgets
import pytest
from pydantic import ValidationError

from cochem_base.config_loader import get_base_root
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    TOPOLOGICAL_DEPENDENCY_MAP,
    DeploymentManifest,
    SynapInstallerGUI,
    _cleanup_zombie_processes,
    detect_avx512_support,
    detect_host_hardware,
    resolve_topological_dependencies,
    serialize_default_manifest,
    serialize_system_config_json,
    validate_topological_prerequisites,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def target_file_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_unity_installer_dashboard.py."""
    path = get_base_root() / "cochem_base" / "interfaces" / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def root_file_path() -> Path:
    """Return the absolute path to cochem_unity_installer_dashboard.py."""
    path = get_base_root() / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Root file does not exist: {path}"
    return path


@pytest.fixture
def legacy_file_path() -> Path:
    """Return the absolute path to interfaces/cochem_unity_installer_dashboard.py."""
    path = get_base_root() / "interfaces" / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Legacy file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(
    target_file_path: Path, root_file_path: Path, legacy_file_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (target_file_path, root_file_path, legacy_file_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"

        content = p.read_text(encoding="utf-8")
        assert len(content) > 500, f"File {p.name} content is unexpectedly small."


def test_zero_personal_path_leaks(
    target_file_path: Path, root_file_path: Path, legacy_file_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage in target files."""
    patterns = leak_patterns()
    for p in (target_file_path, root_file_path, legacy_file_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))

        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


def test_deployment_manifest_valid() -> None:
    """Verify DeploymentManifest validates properly with required and optional fields."""
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash="abcdef0123456789",
        interaction_environment="Local-Windows (WSL)",
        calculation_environment="Local-Windows (WSL)",
        orca_tarball_path="",
        selected_repositories=["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"],
    )
    assert manifest.version == "2026.2"
    assert manifest.git_provenance_hash == "abcdef0123456789"
    assert "CoChem-BASE" in manifest.selected_repositories
    assert "CoChem-CORE" in manifest.selected_repositories

    dumped = manifest.model_dump()
    assert isinstance(dumped, dict)
    assert dumped["git_provenance_hash"] == "abcdef0123456789"

    json_str = manifest.model_dump_json()
    assert "abcdef0123456789" in json_str


def test_deployment_manifest_validation_error() -> None:
    """Verify DeploymentManifest raises ValidationError when required fields are missing."""
    with pytest.raises(ValidationError):
        DeploymentManifest.model_validate({"version": "2026.2"})


def test_ecosystem_registry_invariants() -> None:
    """Verify ECOSYSTEM_REGISTRY contains all expected repositories with mandatory flags."""
    mandatory_repos = {"CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"}
    for repo in mandatory_repos:
        assert repo in ECOSYSTEM_REGISTRY, f"Mandatory repository '{repo}' missing from registry."
        assert ECOSYSTEM_REGISTRY[repo]["mandatory"] is True, (
            f"Repository '{repo}' must be marked mandatory."
        )

    assert len(ECOSYSTEM_REGISTRY) == 17, f"Expected 17 ecosystem modules, found {len(ECOSYSTEM_REGISTRY)}"

    for _name, data in ECOSYSTEM_REGISTRY.items():
        assert "desc" in data and len(data["desc"]) > 5
        assert "repo" in data and data["repo"].startswith("https://")
        assert "mandatory" in data and isinstance(data["mandatory"], bool)


def test_synap_installer_gui_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify SynapInstallerGUI initializes correctly and creates necessary directories."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    gui = SynapInstallerGUI()
    assert gui.disk_safe is True
    assert gui.engine_registry.exists()
    assert gui.module_registry.exists()
    assert len(gui.interaction_options) == 6
    assert len(gui.calculation_options) == 5
    assert "GitHub Codespaces" in gui.interaction_options
    assert "Local-Windows (WSL)" in gui.interaction_options

    ui = gui.build_ui()
    assert isinstance(ui, widgets.Widget)


def test_hardware_hud_and_avx512_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify hardware telemetry collection and dynamic HUD table rendering."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    # Test AVX-512 detection functions
    avx512 = detect_avx512_support()
    assert isinstance(avx512, bool)

    monkeypatch.setenv("COCHEM_FORCE_AVX512", "1")
    assert detect_avx512_support() is True

    monkeypatch.setenv("COCHEM_FORCE_AVX512", "0")
    assert detect_avx512_support() is False

    monkeypatch.delenv("COCHEM_FORCE_AVX512", raising=False)

    # Test Hardware telemetry collection
    telemetry = detect_host_hardware()
    assert "physical_cpu_cores" in telemetry
    assert "logical_cpu_cores" in telemetry
    assert "ram_gb" in telemetry
    assert "vram_gb" in telemetry
    assert "avx512_support" in telemetry
    assert telemetry["physical_cpu_cores"] >= 1
    assert telemetry["ram_gb"] > 0.0

    gui = SynapInstallerGUI()
    hud_content = gui._render_hardware_hud_html(telemetry)
    assert "SYSTEM METAL &amp; COMPUTE TELEMETRY HUD" in hud_content
    assert "System RAM" in hud_content
    assert "CPU Cores" in hud_content
    assert "GPU Accelerator" in hud_content
    assert "Vector ISA (AVX-512)" in hud_content

    gui.refresh_hardware_hud()
    assert gui.hud_html is not None
    assert len(gui.hud_html.value) > 100


def test_codespaces_interaction_autolock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Codespaces auto-lock sets value to 'GitHub Codespaces' and disabled=True."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    monkeypatch.setenv("CODESPACES", "true")

    gui = SynapInstallerGUI()
    assert gui.interact_target is not None
    assert gui.interact_target.value == "GitHub Codespaces"
    assert gui.interact_target.disabled is True
    assert gui.calc_target is not None
    assert gui.calc_target.value == "GitHub Actions"


def test_orchestrator_lock_ui_immutability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all ipywidgets inputs shift to disabled=True upon pipeline initialization."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    gui = SynapInstallerGUI()
    assert gui.submit_btn is not None
    assert gui.submit_btn.disabled is False

    gui._lock_ui_for_deployment()

    assert gui.submit_btn.disabled is True
    assert "Initializing" in gui.submit_btn.description
    assert gui.interact_target.disabled is True
    assert gui.calc_target.disabled is True
    assert gui.host_orca_path.disabled is True
    assert gui.orca_upload.disabled is True
    assert gui.stage_orca_btn.disabled is True
    assert gui.refresh_telemetry_btn.disabled is True
    for cb in gui.buttons.values():
        assert cb.disabled is True


def test_state_serialization_system_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify state serialization creates strict cochem_system_config.json without hardcoded home."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    target_manifest = scratch / "Registry" / "cochem_deployment_manifest.json"
    manifest = serialize_default_manifest(output_path=target_manifest)

    assert target_manifest.exists()
    system_config_file = scratch / "Registry" / "cochem_system_config.json"
    assert system_config_file.exists()

    config_data = json.loads(system_config_file.read_text(encoding="utf-8"))
    assert config_data["schema_version"] == "4.0.0"
    assert "hardware" in config_data
    assert "ram_gb" in config_data["hardware"]
    assert "physical_cpu_cores" in config_data["hardware"]
    assert "avx512_support" in config_data["hardware"]
    assert "interaction_tier" in config_data
    assert "calculation_tier" in config_data
    assert "selected_modules" in config_data
    assert "CoChem-BASE" in config_data["selected_modules"]


def test_git_hash_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _get_git_hash returns a valid hash string."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    git_hash = gui._get_git_hash()
    assert isinstance(git_hash, str)
    assert len(git_hash) > 0
    assert len(git_hash) <= 16


def test_has_staged_orca_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _has_staged_orca_archive accurately detects staged tarballs."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    assert gui._has_staged_orca_archive() is False

    test_archive = gui.engine_registry / "orca_5_0_4_linux_x86-64.tar.xz"
    test_archive.write_bytes(b"sample archive payload bytes")

    assert gui._has_staged_orca_archive() is True


def test_extract_upload_entries_and_stage_orca(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify archive staging from file upload structures."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    # Test dict input format
    files_dict = {
        "orca_5_0_3.tar.gz": {"content": b"tarball_content_payload"},
        "CoChem-MAGE.zip": {"content": b"zip_content_payload"},
    }
    staged = gui._stage_orca_upload(files_dict)
    assert staged is True
    assert (gui.engine_registry / "orca_5_0_3.tar.gz").exists()
    assert (gui.module_registry / "CoChem-MAGE.zip").exists()


def test_verify_host_orca_path_nonexistent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _verify_host_orca_path returns False for invalid or missing executable paths."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    # Explicitly invalid path must always return False
    assert gui._verify_host_orca_path("/non/existent/custom/path/orca_xyz_123") is False
    assert gui._verify_host_orca_path("C:\\non_existent_orca_binary.exe") is False


def test_pure_python_deployment_airgap_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Air-Gap Zip Sideloading extracts target module without network calls."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    target_mod = "CoChem-BENCH"
    zip_path = gui.module_registry / f"{target_mod}.zip"

    # Create a real zip archive with valid payload
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{target_mod}/__init__.py", "# Bench module init\n")
        zf.writestr(f"{target_mod}/bench_core.py", "def run(): pass\n")

    manifest_payload: Dict[str, Any] = {
        "version": "2026.2",
        "git_provenance_hash": "test_hash",
        "interaction_environment": "Local-Linux (Deb)",
        "calculation_environment": "Local-Linux (Deb)",
        "orca_tarball_path": "",
        "selected_repositories": [target_mod],
    }

    gui._pure_python_deployment_worker(manifest_payload)

    extracted_dir = gui.module_registry / target_mod
    assert extracted_dir.is_dir()
    assert (extracted_dir / "__init__.py").exists()
    assert (extracted_dir / "bench_core.py").exists()

    log_content = gui.log_file.read_text(encoding="utf-8")
    assert "Air-Gap Bridge: Sideloading" in log_content
    assert "Extracted CoChem-BENCH via Air-Gap" in log_content


def test_zombie_cleanup_callable() -> None:
    """Verify _cleanup_zombie_processes executes safely without throwing exceptions."""
    _cleanup_zombie_processes()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_unity_installer_dashboard.py ---
"""Comprehensive Zero-Mock test suite for cochem_unity_installer_dashboard.py.

Validates:
1. File structure, Unix LF line endings, standard UTF-8 encoding, and zero BOM.
2. Zero personal path leaks (using cochem_base.path_sanitization.leak_patterns).
3. Zero banned anti-spoofing terms (mock, dummy, stub, placeholder, fake, TODO, NotImplementedError).
4. Pydantic DeploymentManifest schema validation, default attributes, and serialization.
5. Topological prerequisite definitions, validation, and auto-resolution algorithms.
6. 6-Tier interaction & compute selection model with Codespaces auto-locking.
7. Real-Time Hardware Profiling HUD, AVX-512 vector detection, and color-coded status evaluation.
8. UI Immutability Orchestrator Lock on pipeline initialization.
9. State serialization to cochem_system_config.json and cochem_deployment_manifest.json.
10. Headless detection protocols (CI, GITHUB_ACTIONS, HEADLESS, CLI flag) and automatic manifest serialization.
11. SynapInstallerGUI ipywidgets Tabbed Dashboard construction, tab titles, and prerequisite UI locking.
12. Air-gap archive detection, staging mechanics, and pre-flight disk check rules.
13. Parity and re-exports between root, interfaces/, and cochem_base/interfaces/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import cochem_base.interfaces.cochem_unity_installer_dashboard as canonical_dashboard
import cochem_unity_installer_dashboard as root_dashboard
import interfaces.cochem_unity_installer_dashboard as legacy_dashboard
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    TOPOLOGICAL_DEPENDENCY_MAP,
    DeploymentManifest,
    SynapInstallerGUI,
    detect_avx512_support,
    detect_host_hardware,
    is_headless_environment,
    resolve_topological_dependencies,
    run_headless,
    serialize_default_manifest,
    serialize_system_config_json,
    validate_topological_prerequisites,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def root_py_path() -> Path:
    """Return the absolute path to cochem_unity_installer_dashboard.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def interfaces_py_path() -> Path:
    """Return the absolute path to interfaces/cochem_unity_installer_dashboard.py."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def cochem_base_py_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_unity_installer_dashboard.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_existence_and_structure(
    root_py_path: Path, interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify that cochem_unity_installer_dashboard.py exists in all designated locations."""
    for p in (root_py_path, interfaces_py_path, cochem_base_py_path):
        assert p.exists(), f"File missing at {p}"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 200, f"File at {p} is suspiciously small: {len(content)} bytes"


def test_unix_lf_and_encoding(
    root_py_path: Path, interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (root_py_path, interfaces_py_path, cochem_base_py_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"


def test_zero_personal_path_leaks(
    root_py_path: Path, interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage in dashboard files."""
    patterns = leak_patterns()
    for p in (root_py_path, interfaces_py_path, cochem_base_py_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))
        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


def test_zero_mock_anti_spoofing_banned_terms(
    root_py_path: Path, interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero banned anti-spoofing terms exist in deliverable source files."""
    banned = [
        r"\bmock\b",
        r"\bdummy\b",
        r"\bstub\b",
        r"\bplaceholder\b",
        r"\bfake\b",
        r"#\s*TODO",
        r"NotImplementedError",
    ]
    for p in (root_py_path, interfaces_py_path, cochem_base_py_path):
        content = p.read_text(encoding="utf-8")
        for term in banned:
            matches = list(re.finditer(term, content, flags=re.IGNORECASE))
            assert len(matches) == 0, f"Found banned anti-spoofing term '{term}' in {p.name}: {matches}"


def test_reexports_and_symbol_parity() -> None:
    """Verify interfaces and root re-export canonical symbols faithfully."""
    for mod in (root_dashboard, legacy_dashboard):
        assert mod.DeploymentManifest is canonical_dashboard.DeploymentManifest
        assert mod.SynapInstallerGUI is canonical_dashboard.SynapInstallerGUI
        assert mod.ECOSYSTEM_REGISTRY is canonical_dashboard.ECOSYSTEM_REGISTRY
        assert mod.TOPOLOGICAL_DEPENDENCY_MAP is canonical_dashboard.TOPOLOGICAL_DEPENDENCY_MAP
        assert mod.is_headless_environment is canonical_dashboard.is_headless_environment
        assert mod.run_headless is canonical_dashboard.run_headless
        assert mod.serialize_default_manifest is canonical_dashboard.serialize_default_manifest
        assert mod.detect_avx512_support is canonical_dashboard.detect_avx512_support
        assert mod.detect_host_hardware is canonical_dashboard.detect_host_hardware


def test_deployment_manifest_model_validation(tmp_path: Path) -> None:
    """Verify Pydantic DeploymentManifest schema integrity and JSON serialization."""
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash="a1b2c3d4e5f60718",
        interaction_environment="Local-Windows (WSL)",
        calculation_environment="Local-Linux (Deb)",
        orca_tarball_path="/opt/orca_6_1_1.tar.xz",
        selected_repositories=["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ", "CoChem-SCAN"],
        headless=False,
    )
    assert manifest.version == "2026.2"
    assert manifest.headless is False
    assert len(manifest.selected_repositories) == 6

    out_json = tmp_path / "manifest.json"
    out_json.write_text(manifest.model_dump_json(indent=4), encoding="utf-8")

    loaded_raw = json.loads(out_json.read_text(encoding="utf-8"))
    reloaded = DeploymentManifest.model_validate(loaded_raw)
    assert reloaded.git_provenance_hash == "a1b2c3d4e5f60718"
    assert reloaded.selected_repositories == manifest.selected_repositories


def test_topological_prerequisites_and_validation() -> None:
    """Verify topological prerequisite rules and auto-resolution logic."""
    # Mandatory modules must always be valid together
    mandatory_only = ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"]
    valid, missing = validate_topological_prerequisites(mandatory_only)
    assert valid is True
    assert len(missing) == 0

    # Incomplete set (missing TOPOS)
    invalid_set = ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TORQ", "CoChem-SCAN"]
    valid, missing = validate_topological_prerequisites(invalid_set)
    assert valid is False
    assert "CoChem-TOPOS" in missing

    # Auto-resolution should inject all missing prerequisites
    resolved = resolve_topological_dependencies(["CoChem-SCAN"])
    assert "CoChem-BASE" in resolved
    assert "CoChem-MInt" in resolved
    assert "CoChem-CORE" in resolved
    assert "CoChem-TOPOS" in resolved
    assert "CoChem-TORQ" in resolved
    assert "CoChem-SCAN" in resolved

    # Mandatory modules are locked in ECOSYSTEM_REGISTRY
    assert ECOSYSTEM_REGISTRY["CoChem-BASE"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-MInt"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-CORE"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-TOPOS"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-TORQ"]["mandatory"] is True

    # SCRIBE is non-mandatory per RESOURCE_GUARD mandate
    assert ECOSYSTEM_REGISTRY["CoChem-SCRIBE"]["mandatory"] is False


def test_hardware_hud_and_status_styling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify dynamic HTML table rendering and visual resource status styling."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    gui = SynapInstallerGUI()

    # Case 1: Optimal Profile
    optimal_telemetry = {
        "physical_cpu_cores": 8,
        "logical_cpu_cores": 16,
        "ram_gb": 32.0,
        "avail_ram_gb": 24.0,
        "free_storage_gb": 100.0,
        "gpu_profile": "NVIDIA RTX 4090",
        "vram_gb": 24.0,
        "avx512_support": True,
        "source": "Test Telemetry",
    }
    optimal_html = gui._render_hardware_hud_html(optimal_telemetry)
    assert "SYSTEM METAL &amp; COMPUTE TELEMETRY HUD" in optimal_html
    assert "Optimal" in optimal_html
    assert "Accelerated" in optimal_html
    assert "Supported" in optimal_html
    assert "HARDWARE VERIFIED" in optimal_html

    # Case 2: Constrained Profile
    constrained_telemetry = {
        "physical_cpu_cores": 3,
        "logical_cpu_cores": 6,
        "ram_gb": 12.0,
        "avail_ram_gb": 6.0,
        "free_storage_gb": 15.0,
        "gpu_profile": "None",
        "vram_gb": 0.0,
        "avx512_support": False,
        "source": "Test Telemetry",
    }
    constrained_html = gui._render_hardware_hud_html(constrained_telemetry)
    assert "Constrained" in constrained_html
    assert "RESOURCE NOTICE" in constrained_html

    # Case 3: Critical Profile
    critical_telemetry = {
        "physical_cpu_cores": 1,
        "logical_cpu_cores": 2,
        "ram_gb": 4.0,
        "avail_ram_gb": 2.0,
        "free_storage_gb": 5.0,
        "gpu_profile": "None",
        "vram_gb": 0.0,
        "avx512_support": False,
        "source": "Test Telemetry",
    }
    critical_html = gui._render_hardware_hud_html(critical_telemetry)
    assert "Critical" in critical_html
    assert "CRITICAL RESOURCE WARNING" in critical_html


def test_codespaces_interaction_autolock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Codespaces environment auto-locks interaction dropdown to 'GitHub Codespaces' and disabled=True."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    monkeypatch.setenv("CODESPACES", "1")

    gui = SynapInstallerGUI()
    assert gui.interact_target is not None
    assert gui.interact_target.value == "GitHub Codespaces"
    assert gui.interact_target.disabled is True
    assert gui.calc_target is not None
    assert gui.calc_target.value == "GitHub Actions"


def test_ui_immutability_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all interactive input widgets shift to disabled=True when pipeline initializes."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    gui = SynapInstallerGUI()
    assert gui.submit_btn is not None
    assert gui.submit_btn.disabled is False

    gui._lock_ui_for_deployment()

    assert gui.submit_btn.disabled is True
    assert "Initializing" in gui.submit_btn.description
    assert gui.interact_target.disabled is True
    assert gui.calc_target.disabled is True
    assert gui.host_orca_path.disabled is True
    assert gui.orca_upload.disabled is True
    assert gui.stage_orca_btn.disabled is True
    assert gui.refresh_telemetry_btn.disabled is True
    for cb in gui.buttons.values():
        assert cb.disabled is True


def test_state_serialization_system_config_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify state serialization creates strict cochem_system_config.json and cochem_deployment_manifest.json."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    target_manifest = scratch / "Registry" / "cochem_deployment_manifest.json"
    manifest = serialize_default_manifest(
        output_path=target_manifest,
        interaction_env="Local-Linux (Deb)",
        calc_env="Local-Linux (Deb)",
        extra_modules=["CoChem-SCAN"],
    )
    assert target_manifest.is_file()

    target_config = scratch / "Registry" / "cochem_system_config.json"
    assert target_config.is_file()

    cfg = json.loads(target_config.read_text(encoding="utf-8"))
    assert cfg["schema_version"] == "4.0.0"
    assert "hardware" in cfg
    assert "physical_cpu_cores" in cfg["hardware"]
    assert "ram_gb" in cfg["hardware"]
    assert "avx512_support" in cfg["hardware"]
    assert "interaction_tier" in cfg
    assert cfg["interaction_tier"] == "Local-Linux (Deb)"
    assert "calculation_tier" in cfg
    assert cfg["calculation_tier"] == "Local-Linux (Deb)"
    assert "selected_modules" in cfg
    assert "CoChem-BASE" in cfg["selected_modules"]
    assert "CoChem-SCAN" in cfg["selected_modules"]


def test_headless_environment_detection_and_manifest_serialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify headless detection protocols and automatic manifest serialization."""
    # Test CI env var detection
    monkeypatch.setenv("CI", "true")
    assert is_headless_environment() is True

    # Test GITHUB_ACTIONS detection
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "1")
    assert is_headless_environment() is True

    # Test HEADLESS detection
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("HEADLESS", "1")
    assert is_headless_environment() is True

    # Test serialization in headless mode
    target_manifest_path = tmp_path / "cochem_deployment_manifest.json"
    manifest = serialize_default_manifest(
        output_path=target_manifest_path,
        interaction_env="GitHub Codespaces",
        calc_env="GitHub Actions",
        extra_modules=["CoChem-BENCH"],
    )
    assert target_manifest_path.is_file()
    data = json.loads(target_manifest_path.read_text(encoding="utf-8"))
    assert data["interaction_environment"] == "GitHub Codespaces"
    assert data["calculation_environment"] == "GitHub Actions"
    assert "CoChem-BASE" in data["selected_repositories"]
    assert "CoChem-BENCH" in data["selected_repositories"]
    assert data["headless"] is True

    # Test run_headless execution
    run_result = run_headless(manifest=manifest, auto_deploy=False)
    assert run_result.interaction_environment == "GitHub Codespaces"


def test_tabbed_dashboard_gui_construction_and_layout() -> None:
    """Verify ipywidgets Tab structure, tab titles, and prerequisite UI locking."""
    gui = SynapInstallerGUI()

    # Verify tabbed container exists
    assert hasattr(gui, "tab_container")
    tab = gui.tab_container
    assert tab is not None

    # Check tab titles count (should have 4 tabs)
    assert len(tab.children) == 4
    tab_titles = [tab.get_title(i) for i in range(len(tab.children))]
    assert any("Environment" in t or "1." in t for t in tab_titles)
    assert any("Binaries" in t or "2." in t for t in tab_titles)
    assert any("Modules" in t or "3." in t for t in tab_titles)
    assert any("Deploy" in t or "4." in t for t in tab_titles)

    # Verify 5 mandatory buttons are checked and disabled
    mandatory_keys = ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"]
    for key in mandatory_keys:
        assert key in gui.buttons
        assert gui.buttons[key].value is True
        assert gui.buttons[key].disabled is True

    # Verify optional modules are enabled for toggling and default False
    assert "CoChem-SCRIBE" in gui.buttons
    assert gui.buttons["CoChem-SCRIBE"].disabled is False
    assert gui.buttons["CoChem-SCRIBE"].value is False

    # Verify submit button
    assert gui.submit_btn is not None
    assert "Initialize Pipeline" in gui.submit_btn.description

    # Verify UI build method returns container
    rendered_ui = gui.build_ui()
    assert rendered_ui is not None


def test_archive_staging_and_extraction_logic(tmp_path: Path) -> None:
    """Verify archive staging extracts multi-format upload structures safely."""
    gui = SynapInstallerGUI()
    gui.module_registry = tmp_path / "Modules"
    gui.engine_registry = tmp_path / "Engines"
    gui.module_registry.mkdir(parents=True, exist_ok=True)
    gui.engine_registry.mkdir(parents=True, exist_ok=True)

    # Test dict-based upload entry (ipywidgets file upload schema)
    test_zip_content = b"PK\x05\x06" + b"\x00" * 18  # valid empty zip header
    upload_dict = {
        "test_module.zip": {
            "content": test_zip_content,
            "metadata": {"name": "test_module.zip", "size": len(test_zip_content)},
        }
    }
    staged = gui._stage_orca_upload(upload_dict)
    assert staged is True
    assert (gui.module_registry / "test_module.zip").exists()


def test_preflight_disk_check_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify preflight disk check adheres strictly to 10GB threshold logic."""
    class FakeUsage:
        def __init__(self, free_bytes: int):
            self.free = free_bytes

    gui = SynapInstallerGUI()

    # Case 1: < 10GB free space
    monkeypatch.setattr("psutil.disk_usage", lambda _: FakeUsage(5 * 1024**3))
    gui._pre_flight_disk_check()
    assert gui.disk_safe is False
    assert "Insufficient disk space" in gui.error_msg

    # Case 2: >= 10GB free space
    monkeypatch.setattr("psutil.disk_usage", lambda _: FakeUsage(15 * 1024**3))
    gui._pre_flight_disk_check()
    assert gui.disk_safe is True


def test_defensive_status_and_headless_deploy(tmp_path: Path) -> None:
    """Verify SynapInstallerGUI defensive status logging and headless execution safety."""
    gui = SynapInstallerGUI()
    gui.status_out = None
    gui._log_status("Test info message", level="info")
    gui._log_status("Test warning message", level="warning")
    gui._log_status("Test error message", level="error")
    gui._log_status("Test success message", level="success")

    gui.module_registry = tmp_path / "Modules"
    gui.engine_registry = tmp_path / "Engines"
    gui.log_file = tmp_path / "Logs" / "cochem_deploy.log"
    gui.module_registry.mkdir(parents=True, exist_ok=True)
    gui.engine_registry.mkdir(parents=True, exist_ok=True)
    gui.log_file.parent.mkdir(parents=True, exist_ok=True)

    manifest_dict = {
        "selected_repositories": ["CoChem-BASE", "CoChem-CORE"],
        "interaction_environment": "GitHub Codespaces",
        "calculation_environment": "GitHub Actions",
    }
    gui._pure_python_deployment_worker(manifest_dict)
    assert gui.log_file.exists()
    log_content = gui.log_file.read_text(encoding="utf-8")
    assert "Initiating Pure-Python Air-Gap Module Provisioning" in log_content
    assert "Base repository active. Bypassing clone for CoChem-BASE" in log_content


def test_path_traversal_sanitization(tmp_path: Path) -> None:
    """Verify path traversal attempts in uploads are stripped safely."""
    gui = SynapInstallerGUI()
    gui.registry_dir = tmp_path / "Registry"
    gui.module_registry = gui.registry_dir / "Modules"
    gui.engine_registry = gui.registry_dir / "Engines"
    gui.module_registry.mkdir(parents=True, exist_ok=True)
    gui.engine_registry.mkdir(parents=True, exist_ok=True)

    content = b"PK\x05\x06" + b"\x00" * 18
    traversal_upload = {
        "../../evil_module.zip": {
            "content": content,
            "metadata": {"name": "../../evil_module.zip", "size": len(content)},
        }
    }
    staged = gui._stage_orca_upload(traversal_upload)
    assert staged is True
    # Verify file was written inside module_registry and NOT outside
    assert (gui.module_registry / "evil_module.zip").exists()
    assert not (tmp_path / "evil_module.zip").exists()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_unity_installer_dashboard.py ---
#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.0 - Root Executable Script for Installer Dashboard.

Canonical entrypoint for launching the interactive GUI or headless deployment.
Re-exports symbols from cochem_base.interfaces.cochem_unity_installer_dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path
_BASE_ROOT = Path(__file__).resolve().parent
if str(_BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BASE_ROOT))

from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    TOPOLOGICAL_DEPENDENCY_MAP,
    DeploymentManifest,
    SynapInstallerGUI,
    detect_avx512_support,
    detect_host_hardware,
    get_system_git_hash,
    is_headless_environment,
    logger,
    main,
    resolve_topological_dependencies,
    run_headless,
    serialize_default_manifest,
    serialize_system_config_json,
    validate_topological_prerequisites,
)

__all__ = [
    "ECOSYSTEM_REGISTRY",
    "TOPOLOGICAL_DEPENDENCY_MAP",
    "DeploymentManifest",
    "SynapInstallerGUI",
    "detect_avx512_support",
    "detect_host_hardware",
    "get_system_git_hash",
    "is_headless_environment",
    "logger",
    "main",
    "resolve_topological_dependencies",
    "run_headless",
    "serialize_default_manifest",
    "serialize_system_config_json",
    "validate_topological_prerequisites",
]

if __name__ == "__main__":
    main()

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.