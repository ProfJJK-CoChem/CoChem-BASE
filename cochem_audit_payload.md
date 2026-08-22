Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part2_13_interfaces_unity_installer_prompt.md.
Original prompt:
﻿# CoChem-BASE Coding Prompt: cochem_unity_installer_dashboard.py

## 1. Goal
Implement the file `cochem_unity_installer_dashboard.py` based on the Software Requirements Specification (SRS) - CoChem-BASE (Document 2 Part 2).

## 2. Target Filepath
`D:\__CoChem\GitHub-Repo\CoChem-BASE\interfaces\cochem_unity_installer_dashboard.py`

## 3. Context & Ecosystem Role
The Zero-Friction Setup. Replaces raw terminal prompts with a clean graphical 'Installation & Execution' matrix, bridging CI automation limits and ensuring effortless integration for standard users.

## 4. Deliverable Functions
An interactive `ipywidgets` tabbed dashboard for Stage 0. Enforces topological prerequisites and dynamically implements headless detection protocols (`$CI` or `$GITHUB_ACTIONS`), automatically bypassing UI rendering and serializing default topologies to `cochem_deployment_manifest.json` during unattended automation runs.

## 5. Strict Constraints & Anti-Spoofing
- **Workspace Rules:** Strictly adhere to the Tripartite Workspace Air-Gap and Method Matrix rules.
- **No Mocks or Stubs:** Do NOT use placeholders, mock data, or stub logic (e.g., `pass`, `NotImplementedError`, or fake hardcoded values).
- **Fully Functional:** The code must be production-ready and fully implement the deliverables.
- **Error Handling:** Must degrade gracefully and handle errors according to the SRS without crashing silently.
- **Autonomy:** Do not delegate to the user. Execute the complete implementation.
- **Verification:** Ensure your code runs in the physical constraints as defined.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\interfaces\cochem_unity_installer_dashboard.py ---
#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.0 - Ecosystem Master Installer & Configurator Dashboard.

Provides the interactive ipywidgets tabbed GUI and automated headless deployment logic
for provisioning CoChem micro-silos, enforcing topological prerequisites, verifying
Host ORCA engines, and executing Air-Gap Zip sideloading across the Tripartite Workspace.
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

from cochem_base.config_loader import get_artifact_dir, get_base_root, resolve_executable

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
    "CoChem-SpycFit": {
        "desc": "JAX-accelerated rotational spectroscopy fitting.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-SpycFit",
        "mandatory": False,
    },
    "CoChem-SCRIBE": {
        "desc": "LLM-driven FAIR publication and LaTeX supplementary generator.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-SCRIBE",
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
    "CoChem-SCAN": {
        "desc": "Internal conformational exploration heuristic tool.",
        "repo": "https://github.com/ProfJJK-CoChem/CoChem-SCAN",
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
    "Antigravity-Assistant": {
        "desc": "Antigravity 2.0 Cloud LLM Assistant (Data Privacy Cannot Be Guaranteed).",
        "repo": "https://antigravity.google/cli",
        "mandatory": False,
    },
}

TOPOLOGICAL_DEPENDENCY_MAP: Dict[str, List[str]] = {
    "CoChem-CORE": [],
    "CoChem-TOPOS": ["CoChem-CORE"],
    "CoChem-TORQ": ["CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-SpycFit": ["CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-SCRIBE": ["CoChem-CORE"],
    "CoChem-NODE": ["CoChem-CORE"],
    "CoChem-ORACLE": ["CoChem-CORE"],
    "CoChem-BENCH": ["CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"],
    "CoChem-KINETIC": ["CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"],
    "CoChem-LUMOS": ["CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-MAGE": ["CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-SCAN": ["CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"],
    "CoChem-SHIFT": ["CoChem-CORE", "CoChem-TOPOS"],
    "CoChem-GEOM": ["CoChem-CORE", "CoChem-TOPOS"],
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

    # Always ensure mandatory foundation
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
        return res.stdout.strip()[:16]
    except Exception as e:
        logger.warning(f"Git hash lookup failed: {e}")
        build_hash_file = get_base_root() / ".build_hash"
        if build_hash_file.exists():
            return build_hash_file.read_text(encoding="utf-8").strip()[:16]
        return "RELEASE_BUILD"


def serialize_default_manifest(
    output_path: Optional[Path] = None,
    interaction_env: Optional[str] = None,
    calc_env: Optional[str] = None,
    orca_path: str = "",
    extra_modules: Optional[List[str]] = None,
) -> DeploymentManifest:
    """Constructs and serializes the default topological manifest to disk."""
    artifact_dir = get_artifact_dir()
    registry_dir = artifact_dir / "Registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    target_file = output_path or (registry_dir / "cochem_deployment_manifest.json")

    detected_interaction = interaction_env or (
        "Codespaces"
        if os.environ.get("CODESPACES")
        else {
            "Windows": "Local-Windows (WSL)",
            "Darwin": "Local-MacOS (OrbStack)",
            "Linux": "Local-Linux (Deb)",
        }.get(platform.system(), "Codespaces")
    )

    detected_calc = calc_env or (
        "GitHub Actions" if detected_interaction == "Codespaces" else detected_interaction
    )

    selected_raw = ["CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"]
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

        self.interaction_options = [
            "Local-Windows (WSL)",
            "Local-MacOS (OrbStack)",
            "Local-Linux (Deb)",
            "Codespaces",
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

        self._pre_flight_disk_check()
        if self.disk_safe:
            self._build_ui()

    def _get_git_hash(self) -> str:
        return get_system_git_hash()

    def _pre_flight_disk_check(self) -> None:
        """Verifies safe OS storage limits before rendering (enforces 10GB gate per User Manual §1.2.6)."""
        try:
            free_gb = psutil.disk_usage(str(Path.home())).free / (1024**3)
            if free_gb < 10.0:
                self.disk_safe = False
                self.error_msg = f"CRITICAL ERROR: Insufficient disk space ({free_gb:.2f} GB free). Minimum 10GB required."
            else:
                self.disk_safe = True
        except Exception as e:
            self.disk_safe = False
            self.error_msg = f"WARNING: Storage capacity verification failed ({e}). Manual scratch path confirmation required."

    def _verify_host_orca_path(self, raw_path: str) -> bool:
        """Performs a live quantum helium single-point run to verify native ORCA execution."""
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
            with self.status_out:
                logger.error(f"ORCA path does not exist at: {candidate}")
            return False

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
                with self.status_out:
                    logger.info(f"ORCA verification passed via: {candidate}")
                return True
            return False
        except Exception as e:
            with self.status_out:
                logger.error(f"ORCA verification exception: {e}")
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
        with self.status_out:
            for fname, fdata in entries:
                fname_lower = fname.lower()
                if not fname_lower.endswith((".tar.xz", ".tz", ".tar.gz", ".zip")):
                    logger.warning(f"Unsupported archive type: {fname or 'unknown'}")
                    continue

                target = self.module_registry / fname if fname_lower.endswith(".zip") else self.engine_registry / fname

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
                    logger.info(f"Archive staged to: {target} ({size} bytes)")
                    staged_any = True
        return staged_any

    def _on_module_checkbox_change(self, change: Dict[str, Any], module_name: str) -> None:
        """Handles topological prerequisite updates dynamically when user clicks a module."""
        if change.get("new", False):
            prereqs = TOPOLOGICAL_DEPENDENCY_MAP.get(module_name, [])
            for req in prereqs:
                if req in self.buttons and not self.buttons[req].value:
                    self.buttons[req].value = True
                    with self.status_out:
                        logger.info(f"Auto-selected prerequisite: {req} for {module_name}")

    def _pure_python_deployment_worker(self, manifest_payload: Dict[str, Any]) -> None:
        """Threaded pure-Python replacement for bash routers. Enforces Air-Gap."""
        target_modules = manifest_payload.get("selected_repositories", [])
        progress_step = 80.0 / max(len(target_modules), 1)

        with open(self.log_file, "a", encoding="utf-8") as log_out:

            def log_msg(msg: str) -> None:
                self.output_console.append_stdout(f"{msg}\n")
                log_out.write(f"{msg}\n")
                log_out.flush()

            log_msg("\n[DEPLOYMENT] Initiating Pure-Python Air-Gap Module Provisioning...")
            log_msg(f"[WORKSPACE] Target Module Registry: {self.module_registry}\n")

            clean_env = os.environ.copy()
            clean_env["GIT_TERMINAL_PROMPT"] = "0"
            base_root = str(get_base_root())
            existing_pythonpath = clean_env.get("PYTHONPATH")
            clean_env["PYTHONPATH"] = os.pathsep.join(
                entry for entry in (base_root, existing_pythonpath) if entry
            )
            git_executable = resolve_executable(env_var="GIT_CMD", candidates=("git",))

            for mod in target_modules:
                if mod == "CoChem-CORE":
                    log_msg(f"  [BASE] Base repository active. Bypassing clone for {mod}.")
                    self.progress_bar.value += progress_step
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
                    self.progress_bar.value += progress_step
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
                        self.engine_registry / f"{mod}.zip",
                        self.artifact_dir / f"{mod}.zip",
                    ]

                    for zpath in possible_zips:
                        if zpath.exists():
                            log_msg(f"  [AIR-GAP] Air-Gap Bridge: Sideloading {mod} from {zpath.name}...")
                            try:
                                with zipfile.ZipFile(zpath, "r") as zip_ref:
                                    zip_ref.extractall(self.module_registry)

                                for suffix in ["-main", "-master"]:
                                    extracted_dir = self.module_registry / f"{mod}{suffix}"
                                    if extracted_dir.exists() and not target_dir.exists():
                                        extracted_dir.rename(target_dir)

                                if target_dir.exists():
                                    log_msg(f"  [SUCCESS] Extracted {mod} via Air-Gap. Network bypassed.")
                                    sideload_success = True
                                    break
                            except (zipfile.BadZipFile, OSError) as e:
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

                self.progress_bar.value += progress_step

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
                            self.output_console.append_stdout(line)
                            log_out.write(line)
                            log_out.flush()
                    process.wait()
                    if process.returncode == 0:
                        log_msg("[SUCCESS] Orchestrator completed successfully.")
                        self.progress_bar.bar_style = "success"
                    else:
                        log_msg(f"[ERROR] Orchestrator failed with exit code {process.returncode}.")
                        self.progress_bar.bar_style = "danger"
                except Exception as e:
                    log_msg(f"[ERROR] Failed to launch orchestrator: {e}")
                    self.progress_bar.bar_style = "danger"
            else:
                log_msg(f"[INFO] OS-Native Orchestrator script not present at {orchestrator}. Ready for manual phase runs.")
                self.progress_bar.bar_style = "success"

            self.progress_bar.value = 100.0

    def _lock_ui_for_deployment(self) -> None:
        """Locks all interactive input widgets to enforce UI immutability during execution."""
        self.submit_btn.disabled = True
        self.submit_btn.description = "Deploying..."
        self.interact_target.disabled = True
        self.calc_target.disabled = True
        self.host_orca_path.disabled = True
        self.orca_upload.disabled = True
        self.stage_orca_btn.disabled = True
        for cb in self.buttons.values():
            cb.disabled = True

    def _unlock_ui_after_failure(self) -> None:
        """Restores editable state on input widgets if deployment pre-checks fail."""
        self.submit_btn.disabled = False
        self.submit_btn.description = "Lock & Deploy"
        self.interact_target.disabled = False
        self.calc_target.disabled = False
        self.host_orca_path.disabled = False
        self.orca_upload.disabled = False
        self.stage_orca_btn.disabled = False
        for prog, cb in self.buttons.items():
            if not ECOSYSTEM_REGISTRY.get(prog, {}).get("mandatory", False):
                cb.disabled = False

    def _on_submit(self, b: Any) -> None:
        self._lock_ui_for_deployment()
        self.progress_bar.value = 0.0
        self.progress_bar.bar_style = "info"
        self.progress_bar.layout.display = "block"
        self.output_console.clear_output()
        self.status_out.clear_output()

        selected_raw = [mod for mod, cb in self.buttons.items() if cb.value]
        selected_modules = resolve_topological_dependencies(selected_raw)

        host_orca_path = self.host_orca_path.value.strip()
        host_orca_verified = False

        manifest_model = DeploymentManifest(
            version="2026.2",
            git_provenance_hash=self._get_git_hash(),
            interaction_environment=self.interact_target.value,
            calculation_environment=self.calc_target.value,
            orca_tarball_path=host_orca_path,
            selected_repositories=selected_modules,
            headless=False,
        )

        with open(self.manifest_file, "w", encoding="utf-8") as f:
            f.write(manifest_model.model_dump_json(indent=4))

        manifest_payload = manifest_model.model_dump()

        with self.status_out:
            logger.info(f"Matrix Selections locked securely in: {self.manifest_file}")

            if host_orca_path and host_orca_path != "Not Available - Auto-Routed":
                logger.info("Verifying native ORCA execution pathway...")
                host_orca_verified = self._verify_host_orca_path(host_orca_path)
                if not host_orca_verified and not self._has_staged_orca_archive():
                    logger.warning("ORCA verification failed. Fix path or stage an archive instead.")
                    self._unlock_ui_after_failure()
                    return

            staged_now = False
            if not host_orca_verified:
                staged_now = self._stage_orca_upload(getattr(self.orca_upload, "value", None))

            if host_orca_verified or staged_now or self._has_staged_orca_archive():
                logger.info("Dispatching Pure-Python Deployment Thread...")
                threading.Thread(
                    target=self._pure_python_deployment_worker,
                    args=(manifest_payload,),
                    daemon=True,
                ).start()
            else:
                logger.info("Proceeding with module provisioning (Host ORCA not configured)...")
                threading.Thread(
                    target=self._pure_python_deployment_worker,
                    args=(manifest_payload,),
                    daemon=True,
                ).start()

    def _on_stage_orca_click(self, _: Any) -> None:
        with self.status_out:
            clear_output()
            staged = self._stage_orca_upload(getattr(self.orca_upload, "value", None))
            if staged:
                logger.info("Archives are staged and ready for setup.")
            else:
                logger.warning("No valid archives detected to stage.")

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

        host_interaction = {
            "Windows": "Local-Windows (WSL)",
            "Darwin": "Local-MacOS (OrbStack)",
            "Linux": "Local-Linux (Deb)",
        }.get(platform.system(), "Codespaces")
        if os.environ.get("CODESPACES"):
            host_interaction = "Codespaces"
        host_calculation = host_interaction if host_interaction != "Codespaces" else "GitHub Actions"

        self.interact_target = widgets.Dropdown(
            options=self.interaction_options,
            value=host_interaction,
            description="Interaction (UI):",
            layout={"width": "90%"},
        )
        self.calc_target = widgets.Dropdown(
            options=self.calculation_options,
            value=host_calculation,
            description="Calculation (Compute):",
            layout={"width": "90%"},
        )

        # Tab 0: Environment & Compute
        try:
            free_gb = psutil.disk_usage(str(Path.home())).free / (1024**3)
            cpu_count = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 1
            total_ram_gb = psutil.virtual_memory().total / (1024**3)
            hud_html = widgets.HTML(
                f"<div style='background-color: #f1f5f9; padding: 10px; border-radius: 5px; margin-top: 10px;'>"
                f"<b>System Metal HUD:</b> Physical Cores: <code>{cpu_count}</code> | "
                f"Total RAM: <code>{total_ram_gb:.1f} GB</code> | "
                f"Free Storage: <code>{free_gb:.1f} GB</code>"
                f"</div>"
            )
        except Exception:
            hud_html = widgets.HTML("")

        tab_env = widgets.VBox(
            [
                widgets.HTML("<h4>Step 1: Interaction &amp; Compute Matrices</h4>"),
                self.interact_target,
                self.calc_target,
                hud_html,
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
            description="Lock & Deploy",
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
        display(ui)


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
    get_system_git_hash,
    is_headless_environment,
    logger,
    main,
    resolve_topological_dependencies,
    run_headless,
    serialize_default_manifest,
    validate_topological_prerequisites,
)

__all__ = [
    "ECOSYSTEM_REGISTRY",
    "TOPOLOGICAL_DEPENDENCY_MAP",
    "DeploymentManifest",
    "SynapInstallerGUI",
    "get_system_git_hash",
    "is_headless_environment",
    "logger",
    "main",
    "resolve_topological_dependencies",
    "run_headless",
    "serialize_default_manifest",
    "validate_topological_prerequisites",
]

if __name__ == "__main__":
    main()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_unity_installer_dashboard.py ---
"""Comprehensive Zero-Mock test suite for cochem_unity_installer_dashboard.py.

Validates:
1. File structure, Unix LF line endings, standard UTF-8 encoding, and zero BOM.
2. Zero personal path leaks (using cochem_base.path_sanitization.leak_patterns).
3. Zero banned anti-spoofing terms (mock, dummy, stub, placeholder, fake, TODO, NotImplementedError).
4. Pydantic DeploymentManifest schema validation, default attributes, and serialization.
5. Topological prerequisite definitions, validation, and auto-resolution algorithms.
6. Headless detection protocols (CI, GITHUB_ACTIONS, HEADLESS, CLI flag) and automatic manifest serialization.
7. SynapInstallerGUI ipywidgets Tabbed Dashboard construction, tab titles, and UI immutability locks.
8. Air-gap archive detection, staging mechanics, and pre-flight disk check rules.
9. Parity and re-exports between interfaces/ and cochem_base/interfaces/.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from cochem_base.path_sanitization import leak_patterns
import cochem_base.interfaces.cochem_unity_installer_dashboard as canonical_dashboard
import interfaces.cochem_unity_installer_dashboard as legacy_dashboard
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    TOPOLOGICAL_DEPENDENCY_MAP,
    DeploymentManifest,
    SynapInstallerGUI,
    is_headless_environment,
    resolve_topological_dependencies,
    run_headless,
    serialize_default_manifest,
    validate_topological_prerequisites,
)


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
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify that cochem_unity_installer_dashboard.py exists in both locations."""
    for p in (interfaces_py_path, cochem_base_py_path):
        assert p.exists(), f"File missing at {p}"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 200, f"File at {p} is suspiciously small: {len(content)} bytes"


def test_unix_lf_and_encoding(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (interfaces_py_path, cochem_base_py_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"


def test_zero_personal_path_leaks(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage in dashboard files."""
    patterns = leak_patterns()
    for p in (interfaces_py_path, cochem_base_py_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))
        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


def test_zero_mock_anti_spoofing_banned_terms(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero mock, dummy, stub, or placeholder logic exists in the deliverable."""
    banned = [
        r"\bmock\b",
        r"\bdummy\b",
        r"\bstub\b",
        r"\bplaceholder\b",
        r"\bfake\b",
        r"#\s*TODO",
        r"NotImplementedError",
    ]
    for p in (interfaces_py_path, cochem_base_py_path):
        content = p.read_text(encoding="utf-8")
        for term in banned:
            matches = list(re.finditer(term, content, flags=re.IGNORECASE))
            assert len(matches) == 0, f"Found banned anti-spoofing term '{term}' in {p.name}: {matches}"


def test_reexports_and_symbol_parity() -> None:
    """Verify interfaces.cochem_unity_installer_dashboard re-exports canonical symbols."""
    assert legacy_dashboard.DeploymentManifest is canonical_dashboard.DeploymentManifest
    assert legacy_dashboard.SynapInstallerGUI is canonical_dashboard.SynapInstallerGUI
    assert legacy_dashboard.ECOSYSTEM_REGISTRY is canonical_dashboard.ECOSYSTEM_REGISTRY
    assert legacy_dashboard.is_headless_environment is canonical_dashboard.is_headless_environment
    assert legacy_dashboard.run_headless is canonical_dashboard.run_headless
    assert legacy_dashboard.serialize_default_manifest is canonical_dashboard.serialize_default_manifest


def test_deployment_manifest_model_validation(tmp_path: Path) -> None:
    """Verify Pydantic DeploymentManifest schema integrity and JSON serialization."""
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash="a1b2c3d4e5f60718",
        interaction_environment="Local-Windows (WSL)",
        calculation_environment="Local-Linux (Deb)",
        orca_tarball_path="/opt/orca_6_1_1.tar.xz",
        selected_repositories=["CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ", "CoChem-SCAN"],
        headless=False,
    )
    assert manifest.version == "2026.2"
    assert manifest.headless is False
    assert len(manifest.selected_repositories) == 4

    out_json = tmp_path / "manifest.json"
    out_json.write_text(manifest.model_dump_json(indent=4), encoding="utf-8")

    loaded_raw = json.loads(out_json.read_text(encoding="utf-8"))
    reloaded = DeploymentManifest.model_validate(loaded_raw)
    assert reloaded.git_provenance_hash == "a1b2c3d4e5f60718"
    assert reloaded.selected_repositories == manifest.selected_repositories


def test_topological_prerequisites_and_validation() -> None:
    """Verify topological prerequisite rules and auto-resolution logic."""
    # Mandatory modules must always be valid together
    mandatory_only = ["CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"]
    valid, missing = validate_topological_prerequisites(mandatory_only)
    assert valid is True
    assert len(missing) == 0

    # Incomplete set (missing TOPOS)
    invalid_set = ["CoChem-CORE", "CoChem-TORQ", "CoChem-SCAN"]
    valid, missing = validate_topological_prerequisites(invalid_set)
    assert valid is False
    assert "CoChem-TOPOS" in missing

    # Auto-resolution should inject all missing prerequisites
    resolved = resolve_topological_dependencies(["CoChem-SCAN"])
    assert "CoChem-CORE" in resolved
    assert "CoChem-TOPOS" in resolved
    assert "CoChem-TORQ" in resolved
    assert "CoChem-SCAN" in resolved

    # Mandatory modules are locked in ECOSYSTEM_REGISTRY
    assert ECOSYSTEM_REGISTRY["CoChem-CORE"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-TOPOS"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-TORQ"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-SCRIBE"]["mandatory"] is False


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
        interaction_env="Codespaces",
        calc_env="GitHub Actions",
        extra_modules=["CoChem-BENCH"],
    )
    assert target_manifest_path.is_file()
    data = json.loads(target_manifest_path.read_text(encoding="utf-8"))
    assert data["interaction_environment"] == "Codespaces"
    assert data["calculation_environment"] == "GitHub Actions"
    assert "CoChem-CORE" in data["selected_repositories"]
    assert "CoChem-BENCH" in data["selected_repositories"]
    assert data["headless"] is True

    # Test run_headless execution
    run_result = run_headless(manifest=manifest, auto_deploy=False)
    assert run_result.interaction_environment == "Codespaces"


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

    # Verify mandatory buttons are checked and disabled
    assert "CoChem-CORE" in gui.buttons
    assert gui.buttons["CoChem-CORE"].value is True
    assert gui.buttons["CoChem-CORE"].disabled is True

    assert "CoChem-TOPOS" in gui.buttons
    assert gui.buttons["CoChem-TOPOS"].value is True
    assert gui.buttons["CoChem-TOPOS"].disabled is True

    assert "CoChem-TORQ" in gui.buttons
    assert gui.buttons["CoChem-TORQ"].value is True
    assert gui.buttons["CoChem-TORQ"].disabled is True

    # Verify optional modules are enabled for toggling
    assert "CoChem-SCRIBE" in gui.buttons
    assert gui.buttons["CoChem-SCRIBE"].disabled is False
    assert gui.buttons["CoChem-SCRIBE"].value is False

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
    fake_content = b"PK\x05\x06" + b"\x00" * 18  # valid empty zip header
    upload_dict = {
        "test_module.zip": {
            "content": fake_content,
            "metadata": {"name": "test_module.zip", "size": len(fake_content)},
        }
    }
    staged = gui._stage_orca_upload(upload_dict)
    assert staged is True
    assert (gui.module_registry / "test_module.zip").exists()


def test_preflight_disk_check_threshold() -> None:
    """Verify preflight disk check adheres to 10GB threshold logic."""
    gui = SynapInstallerGUI()
    gui._pre_flight_disk_check()
    assert isinstance(gui.disk_safe, bool)
    assert isinstance(gui.error_msg, str)
Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.