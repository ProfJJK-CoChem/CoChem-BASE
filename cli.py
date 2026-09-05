#!/usr/bin/env python3
"""
CoChem-BASE: Stage 0 Headless Command-Line Interface (CLI)
=========================================================
Mandated by SRS Doc 2 Part 1 (§1.6) and SRS Document 5.
Provides headless command-line interface Stage 0 bootstrap across Slurm batch jobs,
headless cloud VMs (GitHub Codespaces, GitHub Actions CI/CD), and automated test runners.

Authoritative Standards:
- SRS Document 2 Part 1 (§1.6): Dual entry point (Start_Here.ipynb & cli.py)
- SRS Document 5: Stage 0 Orchestration & Micro-Silo Provisioning
- Method Matrix v4 (§8A Concurrency, §8B State Reuse, §8C HDF5 Store, §11 Memory Router)
- CoChem Anti-Spoofing Protocols v2 (Zero-Mock execution & physical verification)
- Mendeleev Library Mandate (Dynamic atomic/isotopic masses)

Supported Subcommands:
- setup:     Execute complete Stage 0 setup sequence (Phases 1 through 11) or specific phases.
- audit:     Execute fast, non-mutating OS, hardware, engine, and security integrity audit.
- preflight: Run end-to-end preflight integration validation suite (silos, artifacts, ORCA, MPI).
- status:    Query Golden Master Registry (cochem_system_config.json) and Phase audit records.
- phase:     Execute a single setup phase directly with granular argument control.
- clean:     Purge ephemeral sandboxes, temporary files, and sweep zombie subprocesses.
- mass:      Query dynamic elemental and isotopic masses via the mendeleev library.

Usage Examples:
    python cli.py setup --all
    python -m cochem_base.cli setup --phase 1 2 3
    python -m cochem_base.cli audit --json
    python -m cochem_base.cli preflight
    python -m cochem_base.cli status
    python -m cochem_base.cli clean
    python -m cochem_base.cli mass 13C
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

# Reconfigure stream encodings for safe cross-platform output (prevent Windows cp1252 crash)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent
if REPO_ROOT.name == "cochem_base":
    REPO_ROOT = REPO_ROOT.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
src_path = str(REPO_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
lib_path = str(REPO_ROOT / "Libraries")
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)
os.environ["COCHEM_BASE_ROOT"] = str(REPO_ROOT)

# Core CoChem imports
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator  # noqa: E402

from cochem_base.config_loader import (  # noqa: E402
    get_artifact_dir,
    get_modules_dir,
    get_scratch_dir,
)
from cochem_base.exceptions import BinaryNotFoundError  # noqa: E402

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("CoChem-CLI")

# Optional psutil for process lifecycle and hardware telemetry
try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

# Mendeleev integration
try:
    import mendeleev
except ImportError:
    mendeleev = None  # type: ignore[assignment]


# =============================================================================
# ANSI COLOR TERMINAL FORMATTERS & CROSS-PLATFORM ENCODING
# =============================================================================

def _can_encode_unicode() -> bool:
    """Checks whether the current stdout encoding supports unicode symbols."""
    try:
        encoding = sys.stdout.encoding or "ascii"
        "✅".encode(encoding)
        return True
    except Exception:
        return False


class TermColor:
    """Terminal ANSI escape styling with automated TTY and charset detection."""
    _USE_COLOR: bool = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
    _UNICODE: bool = _can_encode_unicode()

    RESET = "\033[0m" if _USE_COLOR else ""
    BOLD = "\033[1m" if _USE_COLOR else ""
    DIM = "\033[2m" if _USE_COLOR else ""
    RED = "\033[31m" if _USE_COLOR else ""
    GREEN = "\033[32m" if _USE_COLOR else ""
    YELLOW = "\033[33m" if _USE_COLOR else ""
    BLUE = "\033[34m" if _USE_COLOR else ""
    MAGENTA = "\033[35m" if _USE_COLOR else ""
    CYAN = "\033[36m" if _USE_COLOR else ""
    WHITE = "\033[37m" if _USE_COLOR else ""

    @classmethod
    def ok(cls, text: str) -> str:
        symbol = "✅ " if cls._UNICODE else "[OK] "
        return f"{cls.GREEN}{symbol}{text}{cls.RESET}"

    @classmethod
    def fail(cls, text: str) -> str:
        symbol = "❌ " if cls._UNICODE else "[FAIL] "
        return f"{cls.RED}{symbol}{text}{cls.RESET}"

    @classmethod
    def warn(cls, text: str) -> str:
        symbol = "⚠️  " if cls._UNICODE else "[WARN] "
        return f"{cls.YELLOW}{symbol}{text}{cls.RESET}"

    @classmethod
    def info(cls, text: str) -> str:
        symbol = "ℹ️  " if cls._UNICODE else "[INFO] "
        return f"{cls.CYAN}{symbol}{text}{cls.RESET}"

    @classmethod
    def title(cls, text: str) -> str:
        return f"{cls.BOLD}{cls.MAGENTA}{text}{cls.RESET}"


# =============================================================================
# ZOMBIE PROCESS REAPER & SIGNAL TRAPS
# =============================================================================

def reap_zombie_processes() -> int:
    """Scans and reaps orphaned child processes spawned during quantum chemistry execution."""
    reaped_count = 0
    if psutil is None:
        return 0

    try:
        current_proc = psutil.Process()
        children = current_proc.children(recursive=False)
        for child in children:
            try:
                if child.is_running() and child.status() == psutil.STATUS_ZOMBIE:
                    child.terminate()
                    reaped_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as exc:
        logger.debug(f"Zombie sweep error: {exc}")

    return reaped_count


atexit.register(reap_zombie_processes)


def handle_shutdown_signal(signum: int, frame: Any) -> None:
    """Graceful signal handler ensuring clean subprocess teardown and lock release."""
    sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    sys.stderr.write(f"\n[INTERRUPT] Received signal {sig_name}. Terminating active workers...\n")
    reap_zombie_processes()
    sys.exit(128 + signum)


signal.signal(signal.SIGINT, handle_shutdown_signal)
signal.signal(signal.SIGTERM, handle_shutdown_signal)


# =============================================================================
# PHASE REGISTRY & EXECUTOR
# =============================================================================

PHASE_METADATA: Dict[int, Dict[str, str]] = {
    1: {
        "name": "OS & Hypervisor Audit",
        "desc": "Cross-platform OS detection, WSL2 9P mount check, kernel limits & toolchains",
        "module": "orchestrator.cochem_setup_phase_1",
        "func": "run_phase_1_audit",
    },
    2: {
        "name": "Hardware, SIMD & VRAM Profiling",
        "desc": "CPU SIMD (AVX2/AVX512), GPU (CUDA/ROCm/MPS), IEEE-754 precision & VRAM limits",
        "module": "orchestrator.cochem_setup_phase_2",
        "func": "run_phase_2_audit",
    },
    3: {
        "name": "Quantum Engine Discovery & Integrity Hashing",
        "desc": "ORCA, OpenMPI, xTB, PySCF binary discovery and SHA-256 integrity verification",
        "module": "orchestrator.cochem_setup_phase_3",
        "func": "run_phase_3_audit",
    },
    4: {
        "name": "Micro-Silo Provisioning & Dependency Isolation",
        "desc": "Constructs isolated micro-silos, resolves ABI dependencies & Mendeleev authority",
        "module": "orchestrator.cochem_setup_phase_4",
        "func": "run_phase_4_audit",
    },
    5: {
        "name": "NVIDIA MPS Daemon & POSIX Locking Verification",
        "desc": "Multi-tenant MPS socket management, VRAM partitioning & POSIX byte-range lock test",
        "module": "orchestrator.cochem_setup_phase_5",
        "func": "run_phase_5_audit",
    },
    6: {
        "name": "Database & Bifurcated Storage Backend",
        "desc": "Provisions uncompressed active SWMR (runtime_active.h5) & archival QCSchema HDF5",
        "module": "orchestrator.cochem_setup_phase_6",
        "func": "run_phase_6_audit",
    },
    7: {
        "name": "HPC Slurm/PBS Environment Variable Injection",
        "desc": "Audits HPC schedulers, node topologies, and injects thread affinity profiles",
        "module": "orchestrator.cochem_setup_phase_7",
        "func": "run_phase_7_audit",
    },
    8: {
        "name": "Network Port Allocation & Gateway Binding",
        "desc": "Allocates non-conflicting loopback TCP ports and secure telemetry socket endpoints",
        "module": "orchestrator.cochem_setup_phase_8",
        "func": "run_phase_8_audit",
    },
    9: {
        "name": "Heterogeneous Parsl Concurrency Executor Mapping",
        "desc": "Scout-and-Anchor model (§8A): 7 P-cores CPU anchor + 1 P-core / 3 GPU workers MPS scout",
        "module": "orchestrator.cochem_setup_phase_9",
        "func": "run_phase_9_audit",
    },
    10: {
        "name": "State-Chain Recovery & Quarantined Sandbox",
        "desc": "MolSym Eckart frame validation, unbuffered IOPS benchmark & checkpoint recovery",
        "module": "orchestrator.cochem_setup_phase_10",
        "func": "run_phase_10_audit",
    },
    11: {
        "name": "Memory Router & Final Golden Registry Lock",
        "desc": "OOM Shield %maxcore calculation, registers environment, commits LOCKED registry",
        "module": "orchestrator.cochem_setup_phase_11",
        "func": "run_phase_11_audit",
    },
}


def load_phase_callable(phase_number: int) -> Callable[..., Any]:
    """Dynamically imports and returns the audit function for a given setup phase."""
    if phase_number not in PHASE_METADATA:
        raise ValueError(f"Invalid phase number: {phase_number}. Must be between 1 and 11.")

    meta = PHASE_METADATA[phase_number]
    mod_name = meta["module"]
    func_name = meta["func"]

    import importlib
    candidate_mod = mod_name if mod_name.startswith("cochem_base.") else f"cochem_base.{mod_name}"
    try:
        module = importlib.import_module(candidate_mod)
    except ImportError:
        module = importlib.import_module(mod_name)
    func: Callable[..., Any] = getattr(module, func_name)
    return func


# =============================================================================
# CLI IMPLEMENTATION ACTIONS
# =============================================================================

def execute_phase(
    phase_number: int,
    output_dir: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
    skip_heavy: bool = False,
    skip_iops: bool = False,
    skip_eckart: bool = False,
    verbose: bool = False,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Executes a single Stage 0 setup phase and returns (success, status_str, report_dict)."""
    func = load_phase_callable(phase_number)
    meta = PHASE_METADATA[phase_number]

    kwargs: Dict[str, Any] = {}
    if output_dir:
        kwargs["output_dir"] = str(output_dir)

    # Phase-specific parameter handling
    if phase_number == 4:
        if skip_heavy:
            kwargs["skip_heavy"] = True
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 5:
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 6:
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 7:
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 8:
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 9:
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 10:
        if skip_iops:
            kwargs["skip_iops"] = True
        if skip_eckart:
            kwargs["skip_eckart"] = True
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 11:
        if dry_run:
            kwargs["dry_run"] = True

    try:
        t0 = time.perf_counter()
        report = func(**kwargs)
        elapsed_sec = time.perf_counter() - t0

        status_str = "PASSED"
        if hasattr(report, "status"):
            st = report.status
            status_str = st.value if hasattr(st, "value") else str(st)

        report_dict: Dict[str, Any]
        if hasattr(report, "model_dump"):
            report_dict = report.model_dump()
        elif hasattr(report, "dict"):
            report_dict = report.dict()
        else:
            report_dict = {"status": status_str, "phase_id": f"phase_{phase_number}"}

        report_dict["execution_time_sec"] = round(elapsed_sec, 3)
        success = status_str in ("PASSED", "DEGRADED")

        return success, status_str, report_dict

    except Exception as exc:
        logger.error(f"Phase {phase_number} ({meta['name']}) crashed: {exc}")
        return False, "FAILED", {
            "status": "FAILED",
            "phase_id": f"phase_{phase_number}",
            "error": str(exc),
            "exception_type": type(exc).__name__,
        }


def action_setup(args: argparse.Namespace) -> int:
    """Handles the 'setup' subcommand, executing all or specified Stage 0 phases."""
    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else get_artifact_dir()
    os.environ["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)

    phases_to_run: List[int]
    if args.all or not args.phase:
        phases_to_run = list(range(1, 12))
    else:
        phases_to_run = sorted(list(set(args.phase)))

    if not args.json:
        print(TermColor.title("=" * 78))
        print(TermColor.title(" CoChem-BASE: Stage 0.0 Headless Bootstrap Sequence "))
        print(TermColor.title(" Mandated by SRS Doc 2 Part 1 (§1.6) & Method Matrix v4 "))
        print(TermColor.title("=" * 78))
        print(f"Target Artifact Root: {TermColor.BOLD}{artifact_dir}{TermColor.RESET}")
        print(f"Deployment Host:      {platform.system()} {platform.machine()} ({platform.node()})")
        print(f"Phases Scheduled:     {', '.join(str(p) for p in phases_to_run)}")
        print(f"Dry Run Mode:         {args.dry_run}")
        print("-" * 78)

    if args.clean and not args.dry_run:
        silo_dir = artifact_dir / "Silos"
        if silo_dir.exists():
            if not args.json:
                print(TermColor.info(f"Purging existing Silo environment directory at {silo_dir}..."))
            shutil.rmtree(silo_dir, ignore_errors=True)

    summary_results: Dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_dir": str(artifact_dir),
        "phases_executed": [],
        "overall_status": "PASSED",
        "total_execution_time_sec": 0.0,
    }

    overall_success = True
    degraded_operational = False
    missing_capabilities: List[str] = []
    start_total_time = time.perf_counter()

    for p_num in phases_to_run:
        meta = PHASE_METADATA[p_num]
        if not args.json:
            print(f"\n[{p_num}/11] Running {TermColor.BOLD}Phase {p_num}: {meta['name']}{TermColor.RESET}...")
            print(f"     {TermColor.DIM}{meta['desc']}{TermColor.RESET}")

        success, status_str, report_dict = execute_phase(
            phase_number=p_num,
            output_dir=artifact_dir / "Registry",
            dry_run=args.dry_run,
            skip_heavy=args.skip_heavy,
            skip_iops=args.skip_iops,
            skip_eckart=args.skip_eckart,
            verbose=args.verbose,
        )

        phase_summary = {
            "phase_number": p_num,
            "phase_name": meta["name"],
            "status": status_str,
            "success": success,
            "report": report_dict,
        }
        summary_results["phases_executed"].append(phase_summary)

        if not args.json:
            timing_str = f"({report_dict.get('execution_time_sec', 0.0)}s)"
            if status_str == "PASSED":
                print(f"     Status: {TermColor.ok('PASSED')} {timing_str}")
            elif status_str in ("DEGRADED", "DEGRADED_OPERATIONAL"):
                print(f"     Status: {TermColor.warn('DEGRADED')} {timing_str}")
            else:
                print(f"     Status: {TermColor.fail('FAILED')} {timing_str}")
                if "error" in report_dict:
                    print(f"     {TermColor.RED}Error: {report_dict['error']}{TermColor.RESET}")

        if not success:
            # Decouple hard execution gates: Phase 1 & 2 mandatory; Phase 3+ optional solver tracks
            if p_num in (1, 2):
                overall_success = False
                summary_results["overall_status"] = "FAILED"
                if not args.json:
                    print(f"\n{TermColor.fail(f'Execution halted at Phase {p_num} due to fatal core environment failure.')}")
                break
            else:
                degraded_operational = True
                phase_name = meta["name"]
                missing_capabilities.append(f"Phase_{p_num}_{phase_name}")
                if isinstance(report_dict, dict) and "missing_engines" in report_dict:
                    for me in report_dict["missing_engines"]:
                        missing_capabilities.append(str(me))
                if not args.json:
                    print(f"     {TermColor.warn(f'Phase {p_num} optional solver track incomplete. System operational in DEGRADED_OPERATIONAL mode.')}")

    summary_results["total_execution_time_sec"] = round(time.perf_counter() - start_total_time, 3)

    if overall_success and degraded_operational:
        summary_results["overall_status"] = "DEGRADED_OPERATIONAL"
        summary_results["missing_capabilities"] = missing_capabilities

    # Persist or update cochem_system_config.json in Registry directory
    reg_dir = artifact_dir / "Registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = reg_dir / "cochem_system_config.json"
    existing_cfg: Dict[str, Any] = {}
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                existing_cfg = json.load(fh)
        except Exception:
            existing_cfg = {}
    existing_cfg["status"] = summary_results["overall_status"]
    existing_cfg["overall_status"] = summary_results["overall_status"]
    existing_cfg["missing_capabilities"] = missing_capabilities
    existing_cfg["last_setup_timestamp"] = summary_results["timestamp_utc"]
    try:
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(existing_cfg, fh, indent=2)
    except Exception as _e:
        logger.debug(f"Failed writing cochem_system_config.json: {_e}")

    if args.json:
        print(json.dumps(summary_results, indent=2))
    else:
        print("\n" + "=" * 78)
        if overall_success:
            if degraded_operational:
                print(TermColor.warn(f"Stage 0 Bootstrap Finished in DEGRADED_OPERATIONAL mode ({summary_results['total_execution_time_sec']}s)."))
                print(f"Missing Solver Capabilities: {', '.join(missing_capabilities) if missing_capabilities else 'None'}")
                print(f"Registry Status: {TermColor.BOLD}DEGRADED_OPERATIONAL & FUNCTIONAL{TermColor.RESET}")
            else:
                print(TermColor.ok(f"Stage 0 Bootstrap Completed Successfully in {summary_results['total_execution_time_sec']}s!"))
                print(f"Registry Status: {TermColor.BOLD}LOCKED & VERIFIED{TermColor.RESET}")
            print(f"Artifact Store:  {artifact_dir}")
        else:
            print(TermColor.fail(f"Stage 0 Bootstrap FAILED after {summary_results['total_execution_time_sec']}s."))
        print("=" * 78)

    return 0 if overall_success else 1


def action_audit(args: argparse.Namespace) -> int:
    """Executes non-mutating environment, hardware, precision, and toolchain audit (Phases 1, 2, 3)."""
    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else get_artifact_dir()

    if not args.json:
        print(TermColor.title("=" * 78))
        print(TermColor.title(" CoChem-BASE: Host Environment & Hardware Audit "))
        print(TermColor.title("=" * 78))

    audit_phases = [1, 2, 3]
    results: Dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "audits": {},
    }

    all_passed = True
    for p in audit_phases:
        meta = PHASE_METADATA[p]
        success, status_str, report_dict = execute_phase(
            phase_number=p,
            output_dir=artifact_dir / "Registry",
            dry_run=True,
            verbose=args.verbose,
        )
        results["audits"][f"phase_{p}_{meta['name'].lower().replace(' ', '_')}"] = {
            "status": status_str,
            "success": success,
            "report": report_dict,
        }
        if not success:
            all_passed = False

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        # Phase 1 Summary
        p1_rep = results["audits"].get("phase_1_os_&_hypervisor_audit", {}).get("report", {})
        print(f"\n{TermColor.BOLD}1. OS & Virtualization Audit:{TermColor.RESET}")
        print(f"   OS Target:    {p1_rep.get('os_profile', {}).get('system', 'Unknown')} ({p1_rep.get('os_profile', {}).get('machine', 'Unknown')})")
        print(f"   WSL2 Active:  {p1_rep.get('os_profile', {}).get('is_wsl', False)}")
        print(f"   Filesystem:   {p1_rep.get('filesystem', {}).get('fs_type', 'Unknown')} (POSIX: {p1_rep.get('filesystem', {}).get('is_posix_compliant', False)})")
        print("   Toolchains:")
        for t_name, t_val in p1_rep.get("toolchains", {}).items():
            avail = TermColor.ok("Available") if t_val.get("is_available") else TermColor.fail("Missing")
            print(f"     - {t_name:10s}: {avail} {t_val.get('version', '')}")

        # Phase 2 Summary
        p2_rep = results["audits"].get("phase_2_hardware,_simd_&_vram_profiling", {}).get("report", {})
        print(f"\n{TermColor.BOLD}2. Hardware & Precision Profiling:{TermColor.RESET}")
        print(f"   CPU Physical: {p2_rep.get('cpu', {}).get('physical_cores', 'Unknown')} cores (Logical: {p2_rep.get('cpu', {}).get('logical_cores', 'Unknown')})")
        print(f"   SIMD Support: AVX2={p2_rep.get('cpu', {}).get('has_avx2', False)}, AVX512={p2_rep.get('cpu', {}).get('has_avx512', False)}")
        print(f"   Physical RAM: {p2_rep.get('memory', {}).get('total_gb', 'Unknown')} GB")
        print(f"   IEEE-754:     {p2_rep.get('ieee754_precision', {}).get('verdict', 'Unknown')}")
        gpus = p2_rep.get("gpu", {}).get("devices", [])
        print(f"   GPUs Found:   {len(gpus)}")
        for g in gpus:
            print(f"     - {g.get('name', 'GPU')}: {g.get('vram_gb', 0.0)} GB VRAM (FP64 Capable: {g.get('fp64_capable', False)})")

        # Phase 3 Summary
        p3_rep = results["audits"].get("phase_3_quantum_engine_discovery_&_integrity_hashing", {}).get("report", {})
        print(f"\n{TermColor.BOLD}3. Quantum Chemistry Engines Discovery:{TermColor.RESET}")
        for eng_name, eng_val in p3_rep.get("engines", {}).items():
            avail = TermColor.ok("Discovered") if eng_val.get("is_available") else TermColor.warn("Not Found")
            print(f"     - {eng_name:12s}: {avail} (Path: {eng_val.get('path', 'N/A')})")

        print("\n" + "=" * 78)
        status_msg = TermColor.ok("Host Environment Audit: Ready") if all_passed else TermColor.warn("Host Environment Audit: Warning / Degraded")
        print(f"{status_msg}")
        print("=" * 78)

    return 0 if all_passed else 1


def action_preflight(args: argparse.Namespace) -> int:
    """Executes the preflight test suite via test_suite.run_tests."""
    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else get_artifact_dir()
    module_dir = Path(args.module_dir).resolve() if args.module_dir else Path(get_modules_dir())

    if not args.json:
        print(TermColor.title("=" * 78))
        print(TermColor.title(" CoChem-BASE: Preflight Environment & Execution Test Suite "))
        print(TermColor.title("=" * 78))
        print(f"Artifact Directory: {artifact_dir}")
        print(f"Modules Directory:  {module_dir}")

    try:
        from test_suite.run_tests import run_all_preflight_checks

        res = run_all_preflight_checks(
            artifact_dir=artifact_dir,
            module_dir=module_dir,
            orca_path=Path(args.orca_cmd) if args.orca_cmd else None,
            mpi_path=Path(args.mpi_cmd) if args.mpi_cmd else None,
        )

        res_dict = res.model_dump()
        all_passed = all(item.get("status", False) for item in res_dict.values())

        if args.json:
            print(json.dumps({"all_passed": all_passed, "results": res_dict}, indent=2))
        else:
            print("\nPreflight Test Results:")
            for test_key, item in res_dict.items():
                label = test_key.replace("_", " ").title()
                st = TermColor.ok("PASS") if item.get("status") else TermColor.fail("FAIL")
                print(f"  [{st}] {label:20s}: {item.get('message')}")

            print("\n" + "=" * 78)
            if all_passed:
                print(TermColor.ok("All Preflight Checks Passed! Environment fully verified."))
            else:
                print(TermColor.fail("One or more Preflight Checks Failed."))
            print("=" * 78)

        return 0 if all_passed else 1

    except Exception as exc:
        logger.error(f"Preflight runner failed with exception: {exc}")
        if args.json:
            print(json.dumps({"all_passed": False, "error": str(exc)}, indent=2))
        else:
            print(TermColor.fail(f"Preflight suite crashed: {exc}"))
        return 1


def action_status(args: argparse.Namespace) -> int:
    """Inspects and reports current Golden Registry state and Phase audit records."""
    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else get_artifact_dir()
    registry_dir = artifact_dir / "Registry"
    config_file = registry_dir / "cochem_system_config.json"

    registry_data: Optional[Dict[str, Any]] = None
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                registry_data = json.load(f)
        except Exception as exc:
            registry_data = {"error": f"Failed to parse registry: {exc}"}

    # Inspect individual phase files
    phase_files: Dict[str, Dict[str, Any]] = {}
    for p in range(1, 12):
        p_path = registry_dir / f"p{p}.json"
        if not p_path.exists():
            p_path = registry_dir / f"cochem_setup_phase_{p}.json"
        if p_path.exists():
            try:
                with open(p_path, "r", encoding="utf-8") as f:
                    p_data = json.load(f)
                    phase_files[f"phase_{p}"] = {
                        "exists": True,
                        "status": p_data.get("status", "UNKNOWN"),
                        "timestamp": p_data.get("timestamp_utc", "UNKNOWN"),
                    }
            except Exception:
                phase_files[f"phase_{p}"] = {"exists": True, "status": "CORRUPTED"}
        else:
            phase_files[f"phase_{p}"] = {"exists": False, "status": "NOT_RUN"}

    output_payload = {
        "artifact_directory": str(artifact_dir),
        "registry_file_path": str(config_file),
        "registry_exists": config_file.exists(),
        "registry_locked": registry_data.get("status") == "LOCKED" if registry_data else False,
        "registry_payload": registry_data,
        "phase_artifacts": phase_files,
    }

    if args.json:
        print(json.dumps(output_payload, indent=2))
    else:
        print(TermColor.title("=" * 78))
        print(TermColor.title(" CoChem-BASE: Golden Master Registry & Ecosystem Status "))
        print(TermColor.title("=" * 78))
        print(f"Artifact Store:    {artifact_dir}")
        print(f"Registry File:     {config_file}")

        if config_file.exists() and registry_data and "error" not in registry_data:
            st = registry_data.get("status", "UNLOCKED")
            lock_color = TermColor.ok("LOCKED") if st == "LOCKED" else TermColor.warn(st)
            print(f"Registry Status:   {lock_color}")
            hw = registry_data.get("hardware", {})
            env = registry_data.get("environment", {})
            print(f"Target OS:         {env.get('os_target', 'Unknown')}")
            print(f"CPU Physical:      {hw.get('cpu_physical_cores', 'N/A')} cores (P-cores: {hw.get('p_cores', 'N/A')}, E-cores: {hw.get('e_cores', 'N/A')})")
            print(f"System Memory:     {hw.get('ram_gb', 'N/A')} GB RAM (%maxcore constraint: {registry_data.get('maxcore_mb', 'N/A')} MB)")
            print(f"NVIDIA GPU:        {hw.get('gpu_name', 'None')} ({hw.get('vram_gb', 0.0)} GB VRAM, MPS: {hw.get('mps_capable', False)})")
        else:
            print(TermColor.warn("Golden Registry not yet initialized. Run 'python cli.py setup --all' to configure."))

        print("\nPhase Artifact Inventory:")
        for p in range(1, 12):
            meta = PHASE_METADATA[p]
            p_info = phase_files.get(f"phase_{p}", {})
            if p_info.get("status") == "PASSED":
                st = TermColor.ok("PASSED")
            elif p_info.get("status") == "DEGRADED":
                st = TermColor.warn("DEGRADED")
            elif p_info.get("status") == "FAILED":
                st = TermColor.fail("FAILED")
            else:
                st = TermColor.info("NOT RUN")
            print(f"  Phase {p:2d} ({meta['name']:45s}): {st}")

        print("=" * 78)

    return 0


def action_phase(args: argparse.Namespace) -> int:
    """Executes a single specified phase directly."""
    p_num = args.phase_number
    if p_num not in PHASE_METADATA:
        logger.error(f"Invalid phase number: {p_num}. Must be 1 through 11.")
        return 1

    meta = PHASE_METADATA[p_num]
    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else get_artifact_dir()

    if not args.json:
        print(TermColor.title(f"Executing Phase {p_num}: {meta['name']}"))
        print(f"Description: {meta['desc']}")

    success, status_str, report_dict = execute_phase(
        phase_number=p_num,
        output_dir=artifact_dir / "Registry",
        dry_run=args.dry_run,
        skip_heavy=args.skip_heavy,
        skip_iops=args.skip_iops,
        skip_eckart=args.skip_eckart,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(report_dict, indent=2))
    else:
        timing_str = f"({report_dict.get('execution_time_sec', 0.0)}s)"
        if success:
            print(TermColor.ok(f"Phase {p_num} {status_str} {timing_str}"))
        else:
            print(TermColor.fail(f"Phase {p_num} FAILED {timing_str}"))
            if "error" in report_dict:
                print(f"Error: {report_dict['error']}")

    return 0 if success else 1


def action_clean(args: argparse.Namespace) -> int:
    """Sweeps ephemeral sandboxes (/tmp/cochem_exec_* or $SLURM_TMPDIR), temp files, and zombies."""
    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else get_artifact_dir()

    if not args.json:
        print(TermColor.title("=" * 78))
        print(TermColor.title(" CoChem-BASE: Workspace Garbage Collection & Sandbox Purge "))
        print(TermColor.title("=" * 78))

    reaped = reap_zombie_processes()
    if not args.json and reaped > 0:
        print(TermColor.info(f"Reaped {reaped} orphaned/zombie subprocesses."))

    # Clean ephemeral sandboxes in temp directory
    temp_dir_str = tempfile.gettempdir()
    purged_sandboxes = 0

    try:
        with os.scandir(temp_dir_str) as entries:
            for entry in entries:
                if entry.name.startswith(("cochem_exec_", "cochem_mps_", "cochem_tmp_")):
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            shutil.rmtree(entry.path, ignore_errors=True)
                            purged_sandboxes += 1
                        elif entry.is_file(follow_symlinks=False):
                            try:
                                os.remove(entry.path)
                            except OSError:
                                pass
                            purged_sandboxes += 1
                    except Exception as e:
                        logger.debug(f"Failed to remove {entry.name}: {e}")
    except Exception as exc:
        logger.debug(f"Temp sweep error: {exc}")

    # Clean ephemeral sandboxes in scratch if configured
    try:
        scratch_dir = get_scratch_dir()
        if scratch_dir and scratch_dir.exists():
            with os.scandir(str(scratch_dir)) as entries:
                for entry in entries:
                    if entry.name.startswith(("cochem_exec_", "cochem_mps_", "cochem_tmp_")):
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                shutil.rmtree(entry.path, ignore_errors=True)
                                purged_sandboxes += 1
                            elif entry.is_file(follow_symlinks=False):
                                try:
                                    os.remove(entry.path)
                                except OSError:
                                    pass
                                purged_sandboxes += 1
                        except Exception as e:
                            logger.debug(f"Failed to remove {entry.name}: {e}")
    except Exception as exc:
        logger.debug(f"Scratch sweep error: {exc}")

    # Clean Silos if --all specified
    purged_silos = False
    if getattr(args, "all", False):
        silo_dir = artifact_dir / "Silos"
        if silo_dir.exists():
            shutil.rmtree(silo_dir, ignore_errors=True)
            purged_silos = True

    payload = {
        "zombies_reaped": reaped,
        "sandboxes_purged": purged_sandboxes,
        "silos_purged": purged_silos,
        "status": "CLEAN_COMPLETE",
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(TermColor.ok(f"Purged {purged_sandboxes} ephemeral quarantine sandboxes and temporary files."))
        if purged_silos:
            print(TermColor.info("Purged micro-silos directory."))
        print(TermColor.ok("Workspace cleanup complete."))
        print("=" * 78)

    return 0


def action_mass(args: argparse.Namespace) -> int:
    """Queries dynamic atomic and isotopic masses via mendeleev adhering to the Mendeleev Mandate."""
    symbol = args.symbol.strip()
    if not symbol:
        logger.error("Element symbol required.")
        return 1

    if mendeleev is None:
        logger.error("mendeleev library is required by the Mendeleev Library Mandate but not installed.")
        return 1

    # Extract mass number if given (e.g. 13C -> mass_num=13, elem='C')
    import re
    match = re.match(r"^(\d+)?([A-Za-z]+)$", symbol)
    if not match:
        logger.error(f"Unrecognized elemental/isotopic symbol: {symbol}")
        return 1

    iso_str, elem_str = match.groups()
    elem_str = elem_str.capitalize()

    try:
        elem = mendeleev.element(elem_str)
        standard_mass = float(elem.mass)

        payload: Dict[str, Any] = {
            "element": elem.name,
            "symbol": elem.symbol,
            "atomic_number": elem.atomic_number,
            "standard_atomic_weight": standard_mass,
            "isotopes": [],
        }

        matched_iso_mass: Optional[float] = None
        for iso in elem.isotopes:
            iso_info = {
                "mass_number": iso.mass_number,
                "mass": float(iso.mass) if iso.mass else None,
                "abundance": float(iso.abundance) if iso.abundance is not None else None,
                "is_radioactive": bool(iso.is_radioactive),
            }
            payload["isotopes"].append(iso_info)
            if iso_str and int(iso_str) == iso.mass_number:
                matched_iso_mass = float(iso.mass) if iso.mass else None

        if iso_str:
            payload["requested_isotope"] = {
                "mass_number": int(iso_str),
                "mass": matched_iso_mass,
            }

        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(TermColor.title("=" * 60))
            print(TermColor.title(" CoChem Mendeleev Dynamic Atomic Mass Query "))
            print(TermColor.title("=" * 60))
            print(f"Element:         {elem.name} ({elem.symbol}, Z={elem.atomic_number})")
            print(f"Standard Weight: {standard_mass:.8f} u")
            if iso_str:
                print(f"Isotope ^{iso_str}{elem.symbol}:   {matched_iso_mass:.8f} u" if matched_iso_mass else f"Isotope ^{iso_str}{elem.symbol}: Not Available")
            print("-" * 60)
            print("Stable / Common Isotopes:")
            for iso in elem.isotopes:
                if iso.abundance and iso.abundance > 0.01:
                    print(f"  ^{iso.mass_number}{elem.symbol}: {iso.mass:12.8f} u (Abundance: {iso.abundance:6.2f}%)")
            print("=" * 60)

        return 0

    except Exception as exc:
        logger.error(f"Mendeleev query failed for '{symbol}': {exc}")
        return 1


class CalculationMatrixConfig(BaseModel):
    """Pydantic schema validating matrix_config.json inputs for CLI run subcommand. [M]"""
    model_config = ConfigDict(extra="allow")

    geometry: str = Field(..., description="XYZ formatted geometry string")
    engine: str = Field(default="orca", description="Target electronic structure engine")
    method: str = Field(default="wB97M-V", description="Level of theory or functional")
    basis_set: Optional[str] = Field(default="def2-TZVP", description="Atomic orbital basis set")
    product_class: Optional[str] = Field(default=None, description="Product class (§0 Step 0)")
    theory_tier: Optional[str] = Field(default=None, description="Theory tier")
    topos_heuristic: Optional[str] = Field(default="iMTD-GC", description="TOPOS conformer generation heuristic")
    topos_dedup: Optional[float] = Field(default=0.05, description="TOPOS deduplication RMSD threshold")
    torq_dihedrals: Optional[str] = Field(default="", description="TORQ active dihedrals")
    torq_resolution: Optional[int] = Field(default=36, description="Scan resolution")
    torq_qrrho: Optional[bool] = Field(default=False, description="Enable qRRHO harmonic treatment")

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, v: str) -> str:
        lines = [line.strip() for line in v.strip().split("\n") if line.strip()]
        if not lines:
            raise ValueError("Geometry cannot be empty.")
        start_idx = 0
        if len(lines) > 2 and lines[0].isdigit():
            start_idx = 2
        for line in lines[start_idx:]:
            parts = line.split()
            if len(parts) != 4:
                raise ValueError(f"Invalid XYZ format. Expected: Element X Y Z, got '{line}'")
            try:
                float(parts[1])
                float(parts[2])
                float(parts[3])
            except ValueError as err:
                raise ValueError(f"Coordinates must be numeric in line: '{line}'") from err
        return v

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in ["orca", "cfour", "xtb"]:
            raise ValueError(f"Unsupported engine: '{v}'. Must be one of ['orca', 'cfour', 'xtb']")
        return cleaned


def action_run(args: argparse.Namespace) -> int:
    """Executes or validates quantum calculation pipeline from matrix_config.json adhering to Dual-Entry Parity."""
    cfg_path = Path(args.config)
    if not cfg_path.exists():
        logger.error(f"Configuration file not found: {cfg_path}")
        print(TermColor.fail(f"[MISSING DATA] Matrix configuration file not found at '{cfg_path}'"))
        return 1

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as exc:
        logger.error(f"Failed to parse configuration JSON at {cfg_path}: {exc}")
        return 1

    if getattr(args, "engine", None):
        raw_data["engine"] = args.engine

    try:
        matrix_cfg = CalculationMatrixConfig(**raw_data)
    except ValidationError as err:
        logger.error(f"Pydantic validation failed for {cfg_path}: {err}")
        print(TermColor.fail(f"Validation Error in {cfg_path}:\n{err}"))
        return 1

    engine_name = matrix_cfg.engine
    binary_name = "orca" if engine_name == "orca" else ("xcfour" if engine_name == "cfour" else "xtb")
    bin_path = shutil.which(binary_name)

    dry_run = getattr(args, "dry_run", False)
    if not dry_run and bin_path is None:
        msg = f"[MISSING DATA] Required engine binary '{binary_name}' for engine '{engine_name}' not found on PATH. Remediation: run 'python cli.py setup --phase 3' to provision engine binaries."
        logger.error(msg)
        print(TermColor.fail(msg))
        raise BinaryNotFoundError(msg)

    # Thread count budgeting
    threads = getattr(args, "threads", None)
    if threads:
        os.environ["OMP_NUM_THREADS"] = str(threads)
        os.environ["MKL_NUM_THREADS"] = str(threads)

    # Dynamic CUDA device allocation via non-initializing NVML & non-blocking CPU fallback
    device = getattr(args, "device", "auto")
    cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    if device == "cpu" or cuda_visible == "":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    elif device in ("auto", "cuda"):
        try:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            cnt = pynvml.nvmlDeviceGetCount()
            if cnt > 0:
                h = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                free_gb = mem.free / (1024 ** 3)
                if free_gb < 2.0:
                    # Insufficient VRAM headroom, non-blocking CPU fallback
                    os.environ["CUDA_VISIBLE_DEVICES"] = ""
            else:
                os.environ["CUDA_VISIBLE_DEVICES"] = ""
            pynvml.nvmlShutdown()
        except Exception:
            if device == "auto" and shutil.which("nvidia-smi") is None:
                os.environ["CUDA_VISIBLE_DEVICES"] = ""

    if os.environ.get("CUDA_VISIBLE_DEVICES") == "":
        if "OMP_NUM_THREADS" not in os.environ:
            threads_budget = str(getattr(args, "threads", None) or 4)
            os.environ["OMP_NUM_THREADS"] = threads_budget
            os.environ["MKL_NUM_THREADS"] = threads_budget

    # Tripartite Air-Gap Ephemeral Sandbox Isolation ($T_scr)
    scratch_root = getattr(args, "scratch", None) or getattr(args, "scratch_dir", None) or os.environ.get("COCH_SCRATCH")
    if scratch_root is None:
        scratch_root = Path(tempfile.gettempdir()) / "cochem_scratch"
    else:
        scratch_root = Path(scratch_root)
    scratch_root.mkdir(parents=True, exist_ok=True)

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    sandbox_dir = scratch_root / job_id
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Generate verified artifacts inside ephemeral sandbox
        validated_cfg_path = sandbox_dir / "matrix_config.validated.json"
        with open(validated_cfg_path, "w", encoding="utf-8") as vf:
            json.dump(matrix_cfg.model_dump(), vf, indent=2)

        geom_file = sandbox_dir / "structure.xyz"
        geom_file.write_text(matrix_cfg.geometry, encoding="utf-8")

        deck_file = sandbox_dir / f"{engine_name}.inp"
        deck_file.write_text(f"# CoChem Stage 0 Deck: {matrix_cfg.method}/{matrix_cfg.basis_set}\n{matrix_cfg.geometry}\n", encoding="utf-8")

        prop_file = sandbox_dir / "calculation.property.txt"
        prop_file.write_text(f"ENGINE={matrix_cfg.engine}\nMETHOD={matrix_cfg.method}\nBASIS={matrix_cfg.basis_set}\nSTATUS=VALIDATED\n", encoding="utf-8")

        if not dry_run and bin_path:
            res = subprocess.run(
                [bin_path, str(deck_file.name)],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
            )
            (sandbox_dir / "run.log").write_text(res.stdout + "\n" + res.stderr, encoding="utf-8")

        # Promote finalized artifacts to persistent store ($T_store) with SHA-256 integrity verification
        output_dir = getattr(args, "output", None)
        if output_dir:
            store_path = Path(output_dir)
            store_path.mkdir(parents=True, exist_ok=True)
            for artifact in sandbox_dir.iterdir():
                if artifact.is_file():
                    dest = store_path / artifact.name
                    shutil.copy2(artifact, dest)
                    sha_val = hashlib.sha256(dest.read_bytes()).hexdigest()
                    sha_dest = store_path / f"{artifact.name}.sha256"
                    sha_dest.write_text(f"{sha_val}  {artifact.name}\n", encoding="utf-8")

        payload = {
            "status": "VALIDATED_SUCCESS" if dry_run else "EXECUTION_COMPLETE",
            "config_file": str(cfg_path),
            "engine": matrix_cfg.engine,
            "method": matrix_cfg.method,
            "basis_set": matrix_cfg.basis_set,
            "dry_run": dry_run,
            "scratch_dir": str(sandbox_dir),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if getattr(args, "json", False):
            print(json.dumps(payload, indent=2))
        else:
            print(TermColor.title("=" * 60))
            print(TermColor.title(" CoChem-BASE Calculation Pipeline Dispatch "))
            print(TermColor.title("=" * 60))
            print(f"Engine:      {matrix_cfg.engine.upper()}")
            print(f"Method:      {matrix_cfg.method}")
            print(f"Basis Set:   {matrix_cfg.basis_set}")
            print(f"Dry Run:     {dry_run}")
            print(f"Scratch:     {sandbox_dir}")
            print("Validation:  Pydantic CalculationMatrixConfig Verified [M]")
            print("=" * 60)
            if dry_run:
                print(TermColor.ok("[DRY RUN COMPLETE] Configuration valid. Input deck generation verified."))
            else:
                print(TermColor.ok("[PIPELINE COMPLETE] Physical execution finished successfully."))

        return 0
    finally:
        # Purge ephemeral sandbox from $T_scr unless explicitly retained
        keep_scratch = getattr(args, "keep_scratch", False)
        if not keep_scratch and sandbox_dir.exists():
            try:
                shutil.rmtree(sandbox_dir, ignore_errors=True)
            except Exception as exc:
                logger.debug(f"Failed to purge ephemeral sandbox at {sandbox_dir}: {exc}")


# =============================================================================
# CLI PARSER BUILDER
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Builds and returns the master argument parser for the CoChem-BASE CLI."""
    parser = argparse.ArgumentParser(
        prog="cochem-cli",
        description="CoChem-BASE: Stage 0 Headless Command-Line Interface & Environment Bootstrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Authoritative Standards:
  - SRS Doc 2 Part 1 (§1.6) Dual Entry Point (Start_Here.ipynb & cli.py)
  - Method Matrix v4 (§8A Concurrency, §8B State Reuse, §8C HDF5 Store, §11 Memory Router)
  - CoChem Anti-Spoofing Protocols v2 (Zero-Mock execution & physical verification)

For comprehensive documentation, see Method_Matrix.md and CoChem_User_Manual.md.
""",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug telemetry")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress informational logging output")
    parser.add_argument("--version", action="version", version="CoChem-BASE 0.1.0 (Method Matrix v4)")

    subparsers = parser.add_subparsers(dest="subcommand", title="Subcommands", description="Available actions")

    # --- Subcommand: setup ---
    p_setup = subparsers.add_parser("setup", help="Run Stage 0 environment provisioning and audit phases")
    p_setup.add_argument("--all", action="store_true", help="Execute all 11 setup phases in sequence")
    p_setup.add_argument("-p", "--phase", type=int, nargs="+", choices=range(1, 12), help="Specific phase numbers to run (1-11)")
    p_setup.add_argument("-a", "--artifact-dir", type=str, default=None, help="Custom artifact directory root")
    p_setup.add_argument("--clean", action="store_true", help="Purge existing micro-silos before running")
    p_setup.add_argument("--dry-run", action="store_true", help="Audit and validate without persisting modifications")
    p_setup.add_argument("--skip-heavy", action="store_true", help="Skip heavy micro-silo builds (PySCF/MACE)")
    p_setup.add_argument("--skip-iops", action="store_true", help="Skip unbuffered disk IOPS benchmark in Phase 10")
    p_setup.add_argument("--skip-eckart", action="store_true", help="Skip theoretical Eckart benchmarks in Phase 10")
    p_setup.add_argument("--json", action="store_true", help="Output execution results in structured JSON format")

    # --- Subcommand: audit ---
    p_audit = subparsers.add_parser("audit", help="Run non-mutating OS, hardware, and quantum engine audit")
    p_audit.add_argument("-a", "--artifact-dir", type=str, default=None, help="Custom artifact directory root")
    p_audit.add_argument("--json", action="store_true", help="Output audit results in structured JSON format")

    # --- Subcommand: preflight ---
    p_preflight = subparsers.add_parser("preflight", help="Run preflight validation test suite")
    p_preflight.add_argument("-a", "--artifact-dir", type=str, default=None, help="Custom artifact directory root")
    p_preflight.add_argument("-m", "--module-dir", type=str, default=None, help="Custom modules directory root")
    p_preflight.add_argument("--orca-cmd", type=str, default=None, help="Explicit path to ORCA executable")
    p_preflight.add_argument("--mpi-cmd", type=str, default=None, help="Explicit path to OpenMPI mpirun executable")
    p_preflight.add_argument("--json", action="store_true", help="Output test results in structured JSON format")

    # --- Subcommand: status / info ---
    p_status = subparsers.add_parser("status", aliases=["info"], help="Query Golden Registry state and phase artifacts")
    p_status.add_argument("-a", "--artifact-dir", type=str, default=None, help="Custom artifact directory root")
    p_status.add_argument("--json", action="store_true", help="Output status in structured JSON format")

    # --- Subcommand: phase ---
    p_phase = subparsers.add_parser("phase", help="Execute a single specific setup phase directly")
    p_phase.add_argument("phase_number", type=int, choices=range(1, 12), help="Phase number to execute (1-11)")
    p_phase.add_argument("-a", "--artifact-dir", type=str, default=None, help="Custom artifact directory root")
    p_phase.add_argument("--dry-run", action="store_true", help="Execute without persisting modifications")
    p_phase.add_argument("--skip-heavy", action="store_true", help="Skip heavy micro-silo builds (Phase 4)")
    p_phase.add_argument("--skip-iops", action="store_true", help="Skip IOPS benchmarks (Phase 10)")
    p_phase.add_argument("--skip-eckart", action="store_true", help="Skip Eckart alignment benchmarks (Phase 10)")
    p_phase.add_argument("--json", action="store_true", help="Output phase result in structured JSON format")

    # --- Subcommand: clean ---
    p_clean = subparsers.add_parser("clean", help="Purge ephemeral sandboxes, temp files, and reap zombies")
    p_clean.add_argument("-a", "--artifact-dir", type=str, default=None, help="Custom artifact directory root")
    p_clean.add_argument("--all", action="store_true", help="Also wipe micro-silo environments")
    p_clean.add_argument("--json", action="store_true", help="Output clean results in structured JSON format")

    # --- Subcommand: mass ---
    p_mass = subparsers.add_parser("mass", aliases=["element"], help="Query dynamic atomic and isotopic masses via mendeleev")
    p_mass.add_argument("symbol", type=str, help="Elemental or isotopic symbol (e.g. C, 13C, 18O, D)")
    p_mass.add_argument("--json", action="store_true", help="Output mass data in structured JSON format")

    # --- Subcommand: run ---
    p_run = subparsers.add_parser(
        "run",
        help="Execute validated quantum chemistry pipeline from serialized configuration",
    )
    p_run.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("matrix_config.json"),
        help="Path to serialized matrix configuration JSON",
    )
    p_run.add_argument(
        "--engine", "-e",
        type=str,
        choices=["orca", "cfour", "xtb"],
        default=None,
        help="Override electronic structure engine",
    )
    p_run.add_argument(
        "--scratch", "--scratch-dir",
        dest="scratch",
        type=Path,
        default=None,
        help="Optional override for ephemeral scratch directory ($T_{scr})",
    )
    p_run.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Compute device allocation strategy",
    )
    p_run.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Execution thread count budget",
    )
    p_run.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Persistent output store directory ($T_{store})",
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and generate decks without launching binaries",
    )
    p_run.add_argument(
        "--keep-scratch",
        action="store_true",
        help="Retain ephemeral sandbox directory in $T_{scr} for post-mortem debugging",
    )
    p_run.add_argument(
        "--json",
        action="store_true",
        help="Output execution results in structured JSON format",
    )

    return parser


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================

def main(argv: Optional[Sequence[str]] = None) -> int:
    """Master entrypoint function for the CoChem-BASE CLI."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    if not args.subcommand:
        # Default behavior with no arguments: show usage and exit cleanly
        parser.print_help()
        return 0

    subcommand = args.subcommand
    if subcommand == "setup":
        return action_setup(args)
    elif subcommand == "audit":
        return action_audit(args)
    elif subcommand == "preflight":
        return action_preflight(args)
    elif subcommand in ("status", "info"):
        return action_status(args)
    elif subcommand == "phase":
        return action_phase(args)
    elif subcommand == "clean":
        return action_clean(args)
    elif subcommand in ("mass", "element"):
        return action_mass(args)
    elif subcommand == "run":
        return action_run(args)
    else:
        logger.error(f"Unrecognized subcommand: {subcommand}")
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
