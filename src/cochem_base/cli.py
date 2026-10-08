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
- preflight: Verify current setup, isolated runtimes and sealed ecosystem installations.
- status:    Query Golden Master Registry (cochem_system_config.json) and Phase audit records.
- phase:     Execute a single setup phase directly with granular argument control.
- clean:     Inspect registered completed work while preserving runtime and scientific files.
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
import json
import logging
import os
import platform
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

# Reconfigure stream encodings for safe cross-platform output (prevent Windows cp1252 crash)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Source checkouts and installed wheels share this canonical implementation.
# Only the root compatibility launcher bootstraps the source-layout import path.
package_parent = Path(__file__).resolve().parent.parent
REPO_ROOT = package_parent.parent if package_parent.name == "src" else package_parent
os.environ["COCHEM_BASE_ROOT"] = str(REPO_ROOT)

# Core CoChem imports

from cochem_base.config_loader import (  # noqa: E402
    get_artifact_dir,
    get_modules_dir,
)
from cochem_base._version import __version__  # noqa: E402

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
    """Clean only registered CoChem work, leaving other libraries' wait owners intact."""
    from cochem_base.core_engine.cochem_core_subprocess_broker import cleanup_zombie_processes

    return cleanup_zombie_processes()


def handle_shutdown_signal(signum: int, frame: Any) -> None:
    """Unwind executable control flow; no locks, logging, or child waits here."""
    raise SystemExit(128 + signum)


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
        "name": "Memory Router & OOM Shield Audit",
        "desc": "Measures memory bounds and writes the p11 memory-budget audit record",
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
    min_disk_space_gb: float = 50.0,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Executes a single Stage 0 setup phase and returns (success, status_str, report_dict)."""
    func = load_phase_callable(phase_number)
    meta = PHASE_METADATA[phase_number]

    kwargs: Dict[str, Any] = {}
    if output_dir:
        kwargs["output_dir"] = str(output_dir)

    selected_scratch = None
    if output_dir and phase_number in {6, 7, 10}:
        from cochem_base.orchestrator.cochem_setup_phase_7 import select_stage0_scratch
        selected_scratch = select_stage0_scratch(Path(output_dir).parent)

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
        kwargs["min_disk_space_gb"] = min_disk_space_gb
        if output_dir:
            kwargs["scratch_dir"] = str(selected_scratch)
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 7:
        if selected_scratch is not None:
            kwargs["scratch_dir"] = str(selected_scratch)
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 8:
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 9:
        if dry_run:
            kwargs["dry_run"] = True
    elif phase_number == 10:
        if output_dir:
            kwargs["registry_dir"] = str(output_dir)
            kwargs["sandbox_base_dir"] = str(selected_scratch)
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
            report_dict = report.model_dump(mode="json")
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


def action_setup(args: argparse.Namespace, on_event: Optional[Callable[[Dict[str, Any]], None]] = None) -> int:
    """Handles the 'setup' subcommand, executing all or specified Stage 0 phases."""
    if getattr(args, "clean", False):
        failure = {"overall_status": "FAILED", "error": (
            "In-place runtime reset is unsupported. Use BASE's verified update or a new "
            "artifact directory; existing silos, inputs, results and rollback generations are retained.")}
        if on_event:
            on_event({"event": "setup_complete", "summary": failure})
        if args.json and not getattr(args, "native_service", False):
            print(json.dumps(failure))
        elif not args.json:
            print(TermColor.fail(failure["error"]))
        return 1
    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else get_artifact_dir()
    os.environ["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)

    existing_registry = artifact_dir / "Registry" / "cochem_system_config.json"
    if existing_registry.exists() and not args.dry_run:
        from cochem_base.core.cochem_core_registry_manager import load_system_config
        try:
            load_system_config(existing_registry)
        except Exception as exc:
            logger.error("Existing Golden Registry is invalid and was preserved: %s", exc)
            failure = {"overall_status": "FAILED", "registry_error": str(exc)}
            if on_event:
                on_event({"event": "setup_complete", "summary": failure})
            if args.json and not getattr(args, "native_service", False):
                print(json.dumps(failure))
            return 1

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

        if on_event:
            on_event({"event": "phase_start", "phase_number": p_num, "phase_name": meta["name"]})
        success, status_str, report_dict = execute_phase(
            phase_number=p_num,
            output_dir=artifact_dir / "Registry",
            dry_run=args.dry_run,
            skip_heavy=args.skip_heavy,
            skip_iops=args.skip_iops,
            skip_eckart=args.skip_eckart,
            verbose=args.verbose,
            min_disk_space_gb=getattr(args, "min_disk_space_gb", 50.0),
        )

        phase_summary = {
            "phase_number": p_num,
            "phase_name": meta["name"],
            "status": status_str,
            "success": success,
            "report": report_dict,
        }
        summary_results["phases_executed"].append(phase_summary)
        if on_event:
            on_event({"event": "phase_result", **phase_summary})

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
    summary_results["dry_run"] = args.dry_run
    if overall_success and args.dry_run:
        summary_results["overall_status"] = "AUDIT_ONLY"
    elif overall_success and phases_to_run != list(range(1, 12)):
        summary_results["overall_status"] = "PARTIAL_AUDIT"

    # Partial audits must not overwrite the execution authority. The complete
    # registry is assembled once, after all eleven reports are available.
    reg_dir = artifact_dir / "Registry"
    if not args.dry_run:
        from cochem_base.core.cochem_core_registry_manager import atomic_write_json
        from cochem_base.orchestrator.stage0_authority import publish_stage0_authority

        try:
            if overall_success and phases_to_run == list(range(1, 12)):
                registry = publish_stage0_authority(summary_results)
                summary_results["overall_status"] = registry.status
                summary_results["missing_capabilities"] = registry.stage0.unavailable_capabilities
                summary_results["registry_path"] = str(reg_dir / "cochem_system_config.json")
                degraded_operational = registry.status == "DEGRADED_OPERATIONAL"
                missing_capabilities = registry.stage0.unavailable_capabilities
            atomic_write_json(reg_dir / "setup_summary.json", summary_results)
        except (Exception, SystemExit) as exc:
            logger.error("Could not publish complete Stage 0 authority: %s", exc)
            overall_success = False
            summary_results["overall_status"] = "FAILED"
            summary_results["registry_error"] = str(exc)
            atomic_write_json(reg_dir / "setup_summary.json", summary_results)

    if on_event:
        on_event({"event": "setup_complete", "summary": summary_results})
    if args.json:
        if not getattr(args, "native_service", False):
            print(json.dumps(summary_results, indent=2))
    else:
        print("\n" + "=" * 78)
        if overall_success:
            if args.dry_run:
                print(TermColor.ok("Requested audits finished; the registry was not updated."))
            elif summary_results["overall_status"] == "PARTIAL_AUDIT":
                print(TermColor.ok("Requested setup phases finished; the full bootstrap has not been verified."))
            elif degraded_operational:
                print(TermColor.warn(f"Stage 0 Bootstrap Finished in DEGRADED_OPERATIONAL mode ({summary_results['total_execution_time_sec']}s)."))
                print(f"Missing Solver Capabilities: {', '.join(missing_capabilities) if missing_capabilities else 'None'}")
                print(f"Registry Status: {TermColor.BOLD}DEGRADED_OPERATIONAL & FUNCTIONAL{TermColor.RESET}")
            else:
                print(TermColor.ok(f"Stage 0 Bootstrap Completed Successfully in {summary_results['total_execution_time_sec']}s!"))
                print(f"Recorded Setup Status: {TermColor.BOLD}{summary_results['overall_status']}{TermColor.RESET}")
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
    """Revalidate actual setup and installation authority without running science.

    Missing licensed engines are optional. An advertised available runtime must
    satisfy its full authority, and empty provider directories never establish
    an installation. This entrypoint is also available in the installed wheel.
    """
    from filelock import FileLock
    from cochem_base.cochem_core_registry_schema import CoChemSystemConfig
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    from cochem_base.interfaces.module_execution import installed_module_status
    from cochem_base.interfaces.student_setup import DEFAULT_MODULES, _read, validate_runtime_record
    from cochem_base.orchestrator.micro_silo_manager import (
        MicroSiloValidationError, validate_pins, verify_micro_silo,
    )
    from cochem_base.orchestrator.silo_dependency_pins import DEFAULT_PINS

    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else get_artifact_dir()
    module_dir = Path(args.module_dir).resolve() if args.module_dir else artifact_dir / "Modules"
    authority_dir = artifact_dir
    results = {}
    try:
        runtime = _read(artifact_dir / "StudentSetup" / "active-runtime.json")
        if runtime is not None:
            validate_runtime_record(runtime, artifact_dir, REPO_ROOT)
            if runtime.get("kind") == "reviewed-release":
                from scripts.manage_modules import verify_installation
                verify_installation("base", runtime["base_spec"], artifact_dir / "BaseRuntime")
            authority_dir = Path(runtime.get("authority_path", str(artifact_dir))).resolve()
        registry_path = authority_dir / "Registry" / "cochem_system_config.json"
        if registry_path.is_symlink() or not registry_path.is_file():
            raise ValueError("A current regular Golden Registry file is required; run BASE setup first.")
        with FileLock(str(registry_path) + ".lock", timeout=10):
            config = CoChemSystemConfig.model_validate_json(registry_path.read_text(encoding="utf-8"))
        if (config.status not in {"LOCKED", "ACTIVE", "PASSED", "DEGRADED_OPERATIONAL"}
                or not config.verify_checksum() or config.stage0 is None):
            raise ValueError("Preflight requires checksummed complete eleven-phase execution authority.")
        results["registry"] = {"status": "verified", "passed": True, "required": True,
            "scope": "base", "path": str(registry_path), "phases": len(config.stage0.phases)}
    except Exception as exc:
        results["registry"] = {"status": "invalid", "passed": False, "required": True,
            "scope": "base", "reason": str(exc)}
        config = None

    if config is not None:
        for name, lock in (("cochem_core_silo", "core"), ("cochem_ui_silo", "ui")):
            item = {"status": "invalid", "passed": False, "required": True, "scope": "base"}
            try:
                silo = config.stage0.micro_silos.get(name)
                if silo is None or not silo.packages:
                    raise ValueError("The mandatory isolated runtime has no complete package authority.")
                pins = validate_pins(DEFAULT_PINS[lock])
                if any(silo.packages.get(package) != version for package, version in pins.items()):
                    raise ValueError("The mandatory runtime contradicts the reviewed dependency lock.")
                expected_python = Path(silo.root) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                if Path(silo.python_executable).absolute() != expected_python.absolute():
                    raise ValueError("The runtime interpreter is outside its audited micro-silo.")
                verify_micro_silo(silo.root, python_version=silo.python_version,
                    requirements=[f"{package}=={version}" for package, version in sorted(silo.packages.items())],
                    imports=["pydantic", "numpy", "h5py"] if lock == "core" else ["ipywidgets", "voila"])
                item.update(status="verified", passed=True, package_count=len(silo.packages))
            except (Exception, MicroSiloValidationError) as exc:
                item["reason"] = str(exc)
            results[name] = item

        engine_names = set(config.engines) | {"orca", "cfour"}
        overrides = {"orca": getattr(args, "orca_cmd", None), "mpirun": getattr(args, "mpi_cmd", None)}
        engine_names.update(name for name, value in overrides.items() if value)
        for name in sorted(engine_names):
            record = config.engines.get(name)
            available = record is not None and record.status in {"found", "ready"}
            item = {"status": "unavailable", "passed": False,
                "required": bool(overrides.get(name)) or (available and name not in {"orca", "cfour"}),
                "scope": "engine", "optional": True, "scientific_execution_performed": False}
            if not available:
                item["reason"] = "Not installed; dependent operations remain unavailable."
            else:
                try:
                    authorization = authorize_engine_execution(name, registry_path=registry_path,
                        executable=overrides.get(name), cores=1, maxcore_mb=1)
                    item.update(status="verified", passed=True, binary_sha256=authorization.binary_sha256)
                except (Exception, MicroSiloValidationError) as exc:
                    item.update(status="invalid", reason=str(exc))
            results["engine:" + name] = item

    try:
        observations = installed_module_status(module_dir)
        for observed in observations:
            name = observed["module_id"]
            results["module:" + name] = {**observed, "scope": "ecosystem",
                "passed": observed["status"] == "installed", "required": name in DEFAULT_MODULES}
        for name in DEFAULT_MODULES:
            if "module:" + name not in results:
                raise ValueError("The reviewed catalog does not declare the required default providers.")
    except Exception as exc:
        results["modules"] = {"status": "invalid", "passed": False, "required": True,
            "scope": "ecosystem", "reason": str(exc)}

    all_passed = all(item["passed"] for item in results.values() if item["required"])
    base_ready = all(item["passed"] for item in results.values() if item["scope"] == "base")
    payload = {"schema_version": "cochem.preflight/1", "all_passed": all_passed, "base_ready": base_ready,
        "artifact_directory": str(artifact_dir), "modules_directory": str(module_dir),
        "scientific_execution_performed": False, "results": results}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(TermColor.title("CoChem-BASE: current runtime preflight"))
        for name, item in results.items():
            print(f"  {name}: {item['status']} {item.get('reason', '')}")
        print(TermColor.ok("Required runtime authority verified.") if all_passed else
              TermColor.fail("Required runtime authority is missing or invalid; affected operations remain unavailable."))
    return 0 if all_passed else 1


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
    """Inspect only broker-owned work; file reclamation stays with its owner.

    A pathname prefix or a selected artifact root cannot prove the immutable
    generation, absence of live tasks or right to delete another user's files.
    Producers clean their own verified ephemeral lifecycle directories. This
    CLI never resets accepted/rollback runtimes, inputs, results or micro-silos.
    """
    payload = {"zombies_reaped": 0, "sandboxes_purged": 0, "silos_purged": False,
        "status": "CLEAN_COMPLETE", "filesystem_preserved": True,
        "filesystem_cleanup": "Retained; only the creating task's verified lifecycle may reclaim its files."}
    if getattr(args, "all", False):
        payload.update(status="CLEAN_REFUSED", error=(
            "Destructive runtime reset is unsupported. Use BASE's verified update or a new artifact directory."))
    else:
        try:
            from cochem_base.core_engine.cochem_core_subprocess_broker import get_active_popen_processes
            active = get_active_popen_processes()
            payload["active_owned_process_count"] = len(active)
            if active:
                payload.update(status="CLEAN_BLOCKED_ACTIVE_WORK", error=(
                    "Registered calculations are active; finish or cancel them through their owner before cleanup."))
            else:
                from cochem_base.process_cleanup import reap_owned_children
                reap_owned_children()
        except Exception as exc:
            payload.update(status="CLEAN_REFUSED", error=str(exc))
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(TermColor.ok("Registered work inspected; runtime and scientific files retained.")
              if payload["status"] == "CLEAN_COMPLETE" else TermColor.fail(payload["error"]))
    return 0 if payload["status"] == "CLEAN_COMPLETE" else 1


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


# Compatibility exports; the GUI and Python callers use the native service directly.
from cochem_base.calc.calculation_service import (  # noqa: E402,F401
    CalculationMatrixConfig,
    _accept_orca_result,
    parse_run_geometry as _parse_run_geometry,
    run_calculation,
)


def action_run(args: argparse.Namespace) -> int:
    """Return 0 for completed execution/deck preparation, 3 for a pending handoff."""
    try:
        payload = run_calculation(
            args.config, scratch=getattr(args, "scratch", None), output=getattr(args, "output", None),
            threads=getattr(args, "threads", None), device=getattr(args, "device", "auto"),
            maxcore_mb=getattr(args, "maxcore_mb", None),
            dry_run=bool(getattr(args, "dry_run", False)), keep_scratch=bool(getattr(args, "keep_scratch", False)),
            engine=getattr(args, "engine", None),
        )
        print(json.dumps(payload, indent=2) if getattr(args, "json", False) else
              f"{payload['status']}: {payload['output_dir'] or payload['scratch_dir']}")
        return 3 if payload["status"] == "PENDING_INTEGRATION" else 0
    except Exception as exc:
        print(f"Calculation was not accepted: {exc}", file=sys.stderr)
        return 1


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
    parser.add_argument("--version", action="version", version=f"CoChem-BASE {__version__} (Method Matrix v4)")

    subparsers = parser.add_subparsers(dest="subcommand", title="Subcommands", description="Available actions")

    # --- Subcommand: setup ---
    p_setup = subparsers.add_parser("setup", help="Run Stage 0 environment provisioning and audit phases")
    p_setup.add_argument("--all", action="store_true", help="Execute all 11 setup phases in sequence")
    p_setup.add_argument("-p", "--phase", type=int, nargs="+", choices=range(1, 12), help="Specific phase numbers to run (1-11)")
    p_setup.add_argument("-a", "--artifact-dir", type=str, default=None, help="Custom artifact directory root")
    p_setup.add_argument("--min-disk-space-gb", type=float, default=50.0, help="Required free storage capacity for the chosen workload (GB; default 50)")
    p_setup.add_argument("--clean", action="store_true", help="Unsupported destructive reset; existing runtimes are retained")
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
    p_preflight = subparsers.add_parser("preflight", help="Reverify current setup, engine and sealed module authority")
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
    p_clean = subparsers.add_parser("clean", help="Inspect registered work while retaining runtime and scientific files")
    p_clean.add_argument("-a", "--artifact-dir", type=str, default=None, help="Custom artifact directory root")
    p_clean.add_argument("--all", action="store_true", help="Unsupported destructive reset; existing runtimes are retained")
    p_clean.add_argument("--json", action="store_true", help="Output clean results in structured JSON format")

    # --- Subcommand: mass ---
    p_mass = subparsers.add_parser("mass", aliases=["element"], help="Query dynamic atomic and isotopic masses via mendeleev")
    p_mass.add_argument("symbol", type=str, help="Elemental or isotopic symbol (e.g. C, 13C, 18O, D)")
    p_mass.add_argument("--json", action="store_true", help="Output mass data in structured JSON format")

    p_modules = subparsers.add_parser("modules", help="Fetch, install and verify pinned ecosystem modules")
    p_modules.add_argument("module_arguments", nargs=argparse.REMAINDER,
                           help="list, fetch, install or verify followed by module installer options")

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
        choices=["orca", "cfour", "xtb", "pyscf", "qe"],
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
        "--maxcore-mb",
        type=int,
        default=None,
        help="Per-core memory budget in MiB, bounded by the audited registry",
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
    elif subcommand == "modules":
        from scripts.manage_modules import main as modules_main
        return modules_main(args.module_arguments)
    else:
        logger.error(f"Unrecognized subcommand: {subcommand}")
        parser.print_help()
        return 1


def entrypoint() -> int:
    """Arm crash provenance and process cleanup for executable CLI invocation."""
    preliminary = build_cli_parser().parse_args()
    if preliminary.subcommand in {"clean", "preflight"} or (
            preliminary.subcommand == "setup" and preliminary.clean):
        # Inspection/refusal does not own a scientific controller's shutdown.
        # Importing/arming that controller here would also provision diagnostics
        # before an unsupported destructive request can be refused.
        return main()
    from cochem_base.core_engine.cochem_core_telemetry_logger import install_global_excepthook

    install_global_excepthook(chain=True)
    previous_handlers = {}
    try:
        if threading.current_thread() is threading.main_thread():
            for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"):
                if hasattr(signal, name):
                    signum = getattr(signal, name)
                    previous_handlers[signum] = signal.getsignal(signum)
                    signal.signal(signum, handle_shutdown_signal)
        return main()
    finally:
        # Restore even after partial installation or SystemExit/KeyboardInterrupt.
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)
        reap_zombie_processes()


if __name__ == "__main__":
    raise SystemExit(entrypoint())
