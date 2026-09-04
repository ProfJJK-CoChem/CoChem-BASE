#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 2.0 - Configuration Compiler, Fallback Router & Execution Gatekeeper.
Implements:
1. Dynamic Fallback Router: Auto-swapping computational MLFFs & methods (MACE-OFF24m -> g-xTB if GPU VRAM exhausted or AVX-512 missing).
2. Asynchronous templater and execution handshake manager (cryptographic tokens, validation, async template rendering).
3. Micro-silo binary verification: Validating binary existence, permissions, and semver against micro-silos.
4. Hardware-tailored environment generation: OMP_NUM_THREADS, MKL_NUM_THREADS, CUDA_VISIBLE_DEVICES, KMP_AFFINITY, etc.
5. Semantic version pinning, Mendeleev ECP gates, and abstracted HPC schedulers (SLURM, PBS, Local).
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from enum import Enum
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import stat
import sys
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

import psutil
from mendeleev import element
from packaging import version
from pydantic import BaseModel, Field, field_validator

from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_mps_directories,
    get_scratch_dir,
    resolve_executable,
    resolve_mapped_path,
)

try:
    from core_engine.cochem_core_hardware_profiler import HardwareProfiler
except ImportError:
    HardwareProfiler = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-ConfigCompiler")


import atexit
def _reap_zombies() -> None:
    try:
        current_proc = psutil.Process()
        for child in current_proc.children(recursive=True):
            try:
                if child.status() == psutil.STATUS_ZOMBIE:
                    child.wait(timeout=1)
                else:
                    child.terminate()
                    child.wait(timeout=1)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                logger.debug(f"Ignored exception: {_e}")
    except Exception as _e:
        logger.debug(f"Ignored exception: {_e}")

atexit.register(_reap_zombies)

# =============================================================================
# EXCEPTIONS
# =============================================================================


class ECPValidationError(ValueError):
    """Raised when a heavy element lacks a required ECP definition."""
    pass


class CompilerError(Exception):
    """Base exception for Config Compiler errors."""
    pass


class TemplateSyntaxError(CompilerError):
    """Raised when template rendering encounters syntax or variable resolution errors."""
    pass


class HandshakeVerificationError(CompilerError):
    """Raised when cryptographic execution handshake verification fails."""
    pass


class BinaryNotFoundError(CompilerError):
    """Raised when a required computational binary is missing or invalid in micro-silos."""
    pass


class HardwareConstraintError(CompilerError):
    """Raised when hardware requirements for an unroutable task cannot be met."""
    pass


# =============================================================================
# ENUMS & PYDANTIC DATA MODELS
# =============================================================================


class TaskType(str, Enum):
    """Classification of computational workload for resource scheduling."""
    CPU_BOUND = "cpu_bound"
    GPU_MLFF = "gpu_mlff"
    GPU_DFT = "gpu_dft"
    HYBRID_SCOUT_ANCHOR = "hybrid_scout_anchor"
    CONFORMER_SEARCH = "conformer_search"
    ANHARMONIC_VPT2 = "anharmonic_vpt2"
    GENERIC = "generic"


class EngineType(str, Enum):
    """Known computational chemistry and MLFF engines."""
    ORCA = "orca"
    CFOUR = "cfour"
    MACE_OFF24M = "mace_off24m"
    MACE_MP0 = "mace_mp_0"
    AIMNET2 = "aimnet2"
    G_XTB = "g-xtb"
    XTB = "xtb"
    CREST = "crest"
    PYSCF = "pyscf"
    GPU4PYSCF = "gpu4pyscf"
    MOPAC = "mopac"
    R2SCAN_3C = "r2scan_3c"
    GENERIC = "generic"


class HardwareProfileSpec(BaseModel):
    """Hardware profile model describing CPU, GPU, memory, and instruction set capabilities."""
    cpu_count: int = Field(default=8, ge=1, description="Logical CPU threads")
    physical_cores: int = Field(default=8, ge=1, description="Physical CPU cores")
    p_cores: int = Field(default=8, ge=0, description="Performance cores on hybrid CPUs")
    e_cores: int = Field(default=0, ge=0, description="Efficiency cores on hybrid CPUs")
    memory_total_gb: float = Field(default=32.0, gt=0.0, description="Total system RAM in GB")
    memory_available_gb: float = Field(default=24.0, gt=0.0, description="Available system RAM in GB")
    gpu_count: int = Field(default=0, ge=0, description="Number of detected GPUs")
    gpu_vram_gb: float = Field(default=0.0, ge=0.0, description="GPU VRAM in GB per device")
    gpu_device_ids: List[int] = Field(default_factory=list, description="List of CUDA GPU device indices")
    has_avx512: bool = Field(default=False, description="Whether CPU supports AVX-512")
    has_avx2: bool = Field(default=True, description="Whether CPU supports AVX2")
    has_cuda: bool = Field(default=False, description="Whether CUDA execution is available")
    mps_enabled: bool = Field(default=False, description="Whether NVIDIA MPS multiplexing is enabled")
    maxcore_mb: Optional[int] = Field(default=None, description="Explicit maxcore MB limit per thread")

    @classmethod
    def from_system(cls) -> "HardwareProfileSpec":
        """Probe real host system hardware specifications safely without mocks."""
        logical_cpus = psutil.cpu_count(logical=True) or 4
        phys_cpus = psutil.cpu_count(logical=False) or max(1, logical_cpus // 2)
        vmem = psutil.virtual_memory()
        total_ram_gb = vmem.total / (1024.0 ** 3)
        avail_ram_gb = vmem.available / (1024.0 ** 3)

        # Detect CPU ISA flags
        has_avx2 = True
        has_avx512 = False

        if platform.system() == "Linux":
            try:
                with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                    cpuinfo_text = f.read().lower()
                    has_avx2 = "avx2" in cpuinfo_text
                    has_avx512 = "avx512f" in cpuinfo_text or "avx512" in cpuinfo_text
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
        else:
            # On Windows/macOS check environment override or fallback heuristic
            if os.environ.get("COCHEM_FORCE_AVX512", "").strip().lower() in {"1", "true", "yes"}:
                has_avx512 = True
            if os.environ.get("COCHEM_FORCE_AVX2", "").strip().lower() in {"0", "false", "no"}:
                has_avx2 = False

        # Detect CUDA / GPU via HardwareProfiler or environment
        gpu_count = 0
        gpu_vram_gb = 0.0
        has_cuda = False
        gpu_device_ids: List[int] = []

        if HardwareProfiler is not None:
            try:
                hp = HardwareProfiler()
                cuda_info = hp.get_cuda_info()
                if cuda_info.get("cuda_available"):
                    has_cuda = True
                    gpu_count = int(cuda_info.get("gpu_count", 0))
                    details = cuda_info.get("gpu_details", [])
                    if details:
                        gpu_vram_gb = float(details[0].get("memory_total_mb", 0)) / 1024.0
                    gpu_device_ids = list(range(gpu_count))
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

        if gpu_count == 0 and os.environ.get("CUDA_VISIBLE_DEVICES"):
            dev_str = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
            if dev_str:
                parts = [p.strip() for p in dev_str.split(",") if p.strip().isdigit()]
                if parts:
                    gpu_count = len(parts)
                    gpu_device_ids = [int(p) for p in parts]
                    has_cuda = True
                    gpu_vram_gb = 8.0  # default assumption if CUDA_VISIBLE_DEVICES is forced

        return cls(
            cpu_count=logical_cpus,
            physical_cores=phys_cpus,
            p_cores=phys_cpus,
            e_cores=0,
            memory_total_gb=total_ram_gb,
            memory_available_gb=avail_ram_gb,
            gpu_count=gpu_count,
            gpu_vram_gb=gpu_vram_gb,
            gpu_device_ids=gpu_device_ids,
            has_avx512=has_avx512,
            has_avx2=has_avx2,
            has_cuda=has_cuda,
            mps_enabled=bool(os.environ.get("CUDA_MPS_PIPE_DIRECTORY")),
        )


class BinaryVerificationResult(BaseModel):
    """Result of micro-silo binary existence, execution, and version verification."""
    engine_name: str
    is_valid: bool
    executable_path: Optional[str] = None
    exists: bool = False
    is_executable: bool = False
    version: Optional[str] = None
    silo_tier: str = "host"
    error_message: Optional[str] = None


class RouteDecision(BaseModel):
    """Routing decision details generated by the Dynamic Fallback Router."""
    requested_engine: str
    selected_engine: str
    was_fallback: bool = False
    fallback_chain: List[str] = Field(default_factory=list)
    fallback_reason: Optional[str] = None
    binary_path: Optional[str] = None
    allocated_threads: int = 1
    allocated_maxcore_mb: int = 1000
    environment_variables: Dict[str, str] = Field(default_factory=dict)
    execution_tier: str = "cpu"
    timestamp: float = Field(default_factory=time.time)


class HandshakeToken(BaseModel):
    """Cryptographically signed token validating execution bundle integrity."""
    token_id: str
    job_id: str
    config_hash: str
    signature: str
    issued_at: float
    expires_at: float
    nonce: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HandshakeVerificationResult(BaseModel):
    """Result of validating an execution handshake token."""
    is_valid: bool
    token_id: str
    job_id: str
    reason: Optional[str] = None
    expired: bool = False
    signature_valid: bool = False
    hash_valid: bool = False


class CompiledJobBundle(BaseModel):
    """Fully compiled execution package including script, handshake, router, and env."""
    job_name: str
    config_hash: str
    handshake_token: HandshakeToken
    route_decision: RouteDecision
    submission_script: str
    input_deck: Optional[str] = None
    environment_variables: Dict[str, str] = Field(default_factory=dict)
    provenance_header: str
    timestamp: float = Field(default_factory=time.time)


# =============================================================================
# 1. TAILORED ENVIRONMENT VARIABLE GENERATOR
# =============================================================================


class HardwareEnvGenerator:
    """Generates execution environment variables tailored to exact hardware profiles."""

    @staticmethod
    def generate_environment(
        hardware: Union[HardwareProfileSpec, Dict[str, Any]],
        task_type: Union[TaskType, str] = TaskType.CPU_BOUND,
        target_engine: str = "orca",
        reserved_p_cores: int = 1,
        requested_threads: Optional[int] = None,
        memory_fraction: float = 0.75,
        custom_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Synthesizes tailored environment variables based on CPU architecture,
        P/E core partitioning (Scout/Anchor pipeline), and memory safety budgets.
        """
        if isinstance(hardware, dict):
            hw = HardwareProfileSpec(**hardware)
        else:
            hw = hardware

        t_type = task_type.value if isinstance(task_type, TaskType) else str(task_type).lower()
        eng = target_engine.lower()
        env: Dict[str, str] = {}

        # 1. Determine thread allocation
        if requested_threads is not None and requested_threads > 0:
            threads = min(requested_threads, hw.cpu_count)
        elif t_type in ("gpu_mlff", "gpu_dft") and hw.gpu_count > 0:
            # GPU tasks require minimal host worker threads (1-2 cores)
            threads = min(max(1, reserved_p_cores), hw.physical_cores)
        elif t_type == "hybrid_scout_anchor":
            # Reserve P-cores for GPU scout, run CPU anchor on remaining P-cores
            if hw.p_cores > reserved_p_cores:
                threads = hw.p_cores - reserved_p_cores
            else:
                threads = max(1, hw.physical_cores - 1)
        else:
            # Standard CPU bound work: use all physical P-cores or physical core count
            threads = hw.p_cores if hw.p_cores > 0 else hw.physical_cores

        threads = max(1, threads)

        # 2. Thread library bindings (OpenMP, MKL, OpenBLAS, NumExpr, BLIS)
        env["OMP_NUM_THREADS"] = str(threads)
        env["MKL_NUM_THREADS"] = str(threads)
        env["OPENBLAS_NUM_THREADS"] = str(threads)
        env["NUMEXPR_NUM_THREADS"] = str(threads)
        env["VECLIB_MAXIMUM_THREADS"] = str(threads)
        env["BLIS_NUM_THREADS"] = str(threads)
        env["OMP_DYNAMIC"] = "FALSE"

        # 3. CPU Core Pinning & Cache Affinity (Method Matrix §8A)
        env["KMP_AFFINITY"] = "granularity=fine,compact,1,0"
        env["KMP_BLOCKTIME"] = "0"
        env["OMP_PROC_BIND"] = "CLOSE"
        env["OMP_PLACES"] = "cores"

        if hw.p_cores > 0 and hw.e_cores > 0:
            env["KMP_HW_SUBSET"] = f"{threads}c:intel_core,1t"

        # 4. Memory Calculations (%maxcore per core)
        if hw.maxcore_mb is not None and hw.maxcore_mb > 0:
            maxcore_per_thread = hw.maxcore_mb
            safe_ram_mb = maxcore_per_thread * threads
        else:
            safe_ram_mb = int((hw.memory_available_gb * 1024.0) * memory_fraction)
            maxcore_per_thread = max(256, safe_ram_mb // threads)

        env["COCHEM_MAXCORE_MB"] = str(maxcore_per_thread)
        env["ORCA_MAXCORE_MB"] = str(maxcore_per_thread)
        env["PSICHEM_MEMORY_MB"] = str(safe_ram_mb)

        # 5. GPU & CUDA Environment
        is_gpu_engine = ("gpu" in eng) or (
            eng in ("mace_off24m", "mace_mp_0", "aimnet2")
            and hw.gpu_count > 0
            and hw.gpu_vram_gb >= (4.0 if "mace" in eng else 2.0)
        )
        is_hybrid_pipeline = t_type == "hybrid_scout_anchor"
        is_gpu_task = t_type in ("gpu_mlff", "gpu_dft")

        if (is_hybrid_pipeline or (is_gpu_engine and is_gpu_task)) and hw.gpu_count > 0:
            if hw.gpu_device_ids:
                env["CUDA_VISIBLE_DEVICES"] = ",".join(str(d) for d in hw.gpu_device_ids)
            else:
                env["CUDA_VISIBLE_DEVICES"] = "0"
            env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

            if hw.mps_enabled:
                pipe_dir, log_dir = get_mps_directories()
                env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
                env["CUDA_MPS_LOG_DIRECTORY"] = str(log_dir)
                env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = "25"
        else:
            env["CUDA_VISIBLE_DEVICES"] = ""

        # 6. Apply custom environment overlays
        if custom_env:
            for k, v in custom_env.items():
                env[str(k)] = str(v)

        return env


# =============================================================================
# 2. MICRO-SILO BINARY VERIFIER
# =============================================================================


class MicroSiloVerifier:
    """Verifies binary existence, execution permissions, and versioning across micro-silos."""

    def __init__(
        self,
        silo_roots: Optional[List[Union[Path, str]]] = None,
        custom_manifest: Optional[Dict[str, str]] = None,
    ) -> None:
        self.silo_roots: List[Path] = []
        if silo_roots:
            for r in silo_roots:
                self.silo_roots.append(resolve_mapped_path(r))
        else:
            # Default micro-silo search hierarchy
            base_root = get_base_root()
            self.silo_roots.extend([
                base_root / "silos",
                Path.home() / ".cochem" / "silos",
                Path(sys.prefix) / "bin",
                Path(sys.prefix) / "Scripts",
            ])

        self.custom_manifest: Dict[str, str] = custom_manifest or {}

    def verify_binary(
        self,
        engine_name: str,
        candidate_path: Optional[Union[str, Path]] = None,
        min_version: Optional[str] = None,
        check_executable: bool = True,
    ) -> BinaryVerificationResult:
        """
        Validates whether a computational engine binary exists, is executable,
        and meets semver requirements.
        """
        engine_key = engine_name.lower().strip()
        target_path: Optional[Path] = None
        silo_tier = "host"

        # 1. Check explicit candidate path
        if candidate_path:
            p = resolve_mapped_path(candidate_path)
            if p.exists():
                target_path = p
                silo_tier = "custom"

        # 2. Check custom manifest mapping
        if target_path is None and engine_key in self.custom_manifest:
            manifest_val = self.custom_manifest[engine_key]
            p = resolve_mapped_path(manifest_val)
            if p.exists():
                target_path = p
                silo_tier = "manifest"

        # 3. Check micro-silo search roots
        if target_path is None:
            names_to_try = [engine_key]
            if platform.system() == "Windows":
                names_to_try.extend([f"{engine_key}.exe", f"{engine_key}.bat", f"{engine_key}.cmd", f"{engine_key}.py"])

            for root in self.silo_roots:
                for n in names_to_try:
                    direct_check = root / n
                    if direct_check.is_file():
                        target_path = direct_check
                        silo_tier = "micro_silo"
                        break
                    bin_check = root / "bin" / n
                    if bin_check.is_file():
                        target_path = bin_check
                        silo_tier = "micro_silo"
                        break
                if target_path is not None:
                    break

        # 4. Check system PATH via shutil.which / resolve_executable
        if target_path is None:
            resolved = resolve_executable(engine_key)
            if resolved:
                p = Path(resolved)
                if p.is_file():
                    target_path = p
                    silo_tier = "host_path"

        # 5. Handle missing binary
        if target_path is None or not target_path.exists():
            return BinaryVerificationResult(
                engine_name=engine_name,
                is_valid=False,
                executable_path=None,
                exists=False,
                is_executable=False,
                silo_tier=silo_tier,
                error_message=f"Binary for '{engine_name}' not found in silos or PATH.",
            )

        # 6. Check file execution permissions
        is_exec = False
        if platform.system() == "Windows":
            # On Windows, file existence + executable extension or read permission constitutes executable binary
            is_exec = target_path.suffix.lower() in {".exe", ".bat", ".cmd", ".py", ""} and target_path.stat().st_size >= 0
        else:
            is_exec = os.access(str(target_path), os.X_OK) or os.access(str(target_path), os.R_OK)

        if check_executable and not is_exec:
            return BinaryVerificationResult(
                engine_name=engine_name,
                is_valid=False,
                executable_path=str(target_path),
                exists=True,
                is_executable=False,
                silo_tier=silo_tier,
                error_message=f"Binary '{target_path}' exists but lacks execution permissions.",
            )

        # 7. Check minimum version if requested
        detected_version: Optional[str] = None
        if min_version:
            try:
                import subprocess
                proc = subprocess.run(
                    [str(target_path), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=True,
                )
                out = proc.stdout + " " + proc.stderr
                v_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", out)
                if v_match:
                    detected_version = v_match.group(1)
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

            if detected_version and version.parse(detected_version) < version.parse(min_version):
                return BinaryVerificationResult(
                    engine_name=engine_name,
                    is_valid=False,
                    executable_path=str(target_path),
                    exists=True,
                    is_executable=True,
                    version=detected_version,
                    silo_tier=silo_tier,
                    error_message=f"Version '{detected_version}' is below required minimum '{min_version}'.",
                )

        return BinaryVerificationResult(
            engine_name=engine_name,
            is_valid=True,
            executable_path=str(target_path),
            exists=True,
            is_executable=True,
            version=detected_version,
            silo_tier=silo_tier,
        )

    def verify_all_silos(self, engines: Union[List[str], Dict[str, str]]) -> Dict[str, BinaryVerificationResult]:
        """Batch verify multiple computational engines."""
        results: Dict[str, BinaryVerificationResult] = {}
        if isinstance(engines, dict):
            for eng_name, cand_path in engines.items():
                results[eng_name] = self.verify_binary(eng_name, candidate_path=cand_path)
        else:
            for eng_name in engines:
                results[eng_name] = self.verify_binary(eng_name)
        return results


# =============================================================================
# 3. DYNAMIC FALLBACK ROUTER
# =============================================================================


class DynamicFallbackRouter:
    """
    Implements dynamic runtime routing and engine auto-swapping based on
    Method Matrix §8.3, §8A, and §9B physical resource constraints.
    """

    def __init__(self, custom_rules: Optional[Dict[str, List[str]]] = None) -> None:
        # Default canonical fallback hierarchies
        self.fallback_hierarchies: Dict[str, List[str]] = {
            "mace_off24m": ["mace_off24m", "aimnet2", "g-xtb", "r2scan_3c"],
            "mace_mp_0": ["mace_mp_0", "aimnet2", "g-xtb", "r2scan_3c"],
            "aimnet2": ["aimnet2", "g-xtb", "r2scan_3c"],
            "gpu4pyscf": ["gpu4pyscf", "pyscf", "orca"],
            "cfour_anharmonic": ["cfour", "orca", "pyscf"],
            "dlpno_ccsd_t": ["dlpno_ccsd_t", "wb97m_v_def2_qzvpp", "r2scan_3c"],
            "goat_aimnet2": ["goat_aimnet2", "goat_xtb2"],
            "crest_gfn2": ["crest_gfn2", "crest_gfnff"],
        }
        if custom_rules:
            self.fallback_hierarchies.update(custom_rules)

        self._custom_evaluators: Dict[str, Callable[[HardwareProfileSpec, Dict[str, Any]], Tuple[bool, Optional[str]]]] = {}

    def register_custom_fallback(
        self,
        engine: str,
        fallback_chain: List[str],
        condition_evaluator: Optional[Callable[[HardwareProfileSpec, Dict[str, Any]], Tuple[bool, Optional[str]]]] = None,
    ) -> None:
        """Register custom engine fallback rule and predicate evaluator."""
        self.fallback_hierarchies[engine.lower()] = fallback_chain
        if condition_evaluator:
            self._custom_evaluators[engine.lower()] = condition_evaluator

    def resolve_route(
        self,
        requested_engine: str,
        hardware: Union[HardwareProfileSpec, Dict[str, Any]],
        silo_verifier: Optional[MicroSiloVerifier] = None,
        task_constraints: Optional[Dict[str, Any]] = None,
        task_type: Union[TaskType, str] = TaskType.CPU_BOUND,
    ) -> RouteDecision:
        """
        Dynamically resolves the optimal executable engine given physical hardware
        and micro-silo status.
        """
        if isinstance(hardware, dict):
            hw = HardwareProfileSpec(**hardware)
        else:
            hw = hardware

        constraints = task_constraints or {}
        req_key = requested_engine.lower().strip()
        chain = self.fallback_hierarchies.get(req_key, [req_key])
        fallback_reason: Optional[str] = None
        selected_engine: Optional[str] = None
        selected_binary: Optional[str] = None
        was_fallback = False

        for candidate in chain:
            cand_key = candidate.lower().strip()
            ok, reason = self._evaluate_engine_capability(cand_key, hw, constraints)
            if not ok:
                fallback_reason = reason
                was_fallback = True
                continue

            # Check binary availability in micro-silo if verifier explicitly provided
            if silo_verifier is not None:
                bin_res = silo_verifier.verify_binary(cand_key)
                if not bin_res.is_valid:
                    fallback_reason = f"Binary for '{cand_key}' unavailable: {bin_res.error_message}"
                    was_fallback = True
                    continue
                selected_binary = bin_res.executable_path

            selected_engine = cand_key
            break

        if selected_engine is None:
            # If all candidates exhausted, select last available or raise error
            selected_engine = chain[-1]
            was_fallback = True
            if fallback_reason is None:
                fallback_reason = "All candidates failed hardware or binary verification."

        # Synthesize tailored environment for chosen engine
        tailored_env = HardwareEnvGenerator.generate_environment(
            hardware=hw,
            task_type=task_type,
            target_engine=selected_engine,
            requested_threads=constraints.get("requested_threads"),
            memory_fraction=constraints.get("memory_fraction", 0.75),
        )

        allocated_threads = int(tailored_env.get("OMP_NUM_THREADS", "1"))
        allocated_maxcore = int(tailored_env.get("COCHEM_MAXCORE_MB", "1000"))

        exec_tier = "gpu" if tailored_env.get("CUDA_VISIBLE_DEVICES") != "" else "cpu"

        return RouteDecision(
            requested_engine=requested_engine,
            selected_engine=selected_engine,
            was_fallback=was_fallback and (selected_engine != req_key),
            fallback_chain=chain,
            fallback_reason=fallback_reason if (selected_engine != req_key) else None,
            binary_path=selected_binary,
            allocated_threads=allocated_threads,
            allocated_maxcore_mb=allocated_maxcore,
            environment_variables=tailored_env,
            execution_tier=exec_tier,
        )

    def _evaluate_engine_capability(
        self,
        engine: str,
        hw: HardwareProfileSpec,
        constraints: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """Evaluates hardware constraints for a candidate engine."""
        # 1. Custom evaluator check
        if engine in self._custom_evaluators:
            return self._custom_evaluators[engine](hw, constraints)

        # 2. MACE-OFF24m / MACE-MP-0 rules
        if engine in ("mace_off24m", "mace_mp_0", "mace"):
            # Requires GPU with VRAM >= 4.0 GB or CPU with AVX-512 and RAM >= 8.0 GB
            if hw.gpu_count > 0 and hw.gpu_vram_gb >= 4.0:
                return True, None
            if hw.has_avx512 and hw.memory_available_gb >= 8.0:
                return True, None
            if hw.gpu_count == 0:
                return False, f"GPU unavailable and CPU lacks AVX-512 for {engine}"
            return False, f"GPU VRAM {hw.gpu_vram_gb:.1f}GB < required 4.0GB for {engine}"

        # 3. AIMNet2 rules
        if engine == "aimnet2":
            # Requires GPU with VRAM >= 2.0 GB or AVX2 on CPU
            if hw.gpu_count > 0 and hw.gpu_vram_gb >= 2.0:
                return True, None
            if hw.has_avx2:
                return True, None
            return False, "AIMNet2 requires GPU with >=2GB VRAM or AVX2 instruction set."

        # 4. gpu4pyscf rules (Method Matrix §8.3 Crossover Rule)
        if engine == "gpu4pyscf":
            if hw.gpu_count == 0:
                return False, "gpu4pyscf requires CUDA-capable GPU."
            if hw.gpu_vram_gb < 6.0:
                return False, f"gpu4pyscf requires >=6.0GB VRAM (found {hw.gpu_vram_gb:.1f}GB)."
            basis_count = constraints.get("basis_functions", 100)
            if basis_count < 50:
                return False, f"Basis count {basis_count} < 50: CPU PySCF faster than GPU (Method Matrix §8.3 crossover)."
            return True, None

        # 5. High-memory DLPNO-CCSD(T)
        if engine == "dlpno_ccsd_t":
            req_ram = constraints.get("min_ram_gb", 16.0)
            if hw.memory_available_gb < req_ram:
                return False, f"DLPNO-CCSD(T) requires >={req_ram}GB RAM (available: {hw.memory_available_gb:.1f}GB)."
            return True, None

        # 6. g-xTB / xTB / CREST / MOPAC / r2SCAN-3c: lightweight CPU compatible
        if engine in ("g-xtb", "xtb", "crest", "crest_gfn2", "crest_gfnff", "mopac", "r2scan_3c", "orca", "pyscf", "cfour"):
            return True, None

        # Default pass
        return True, None


# =============================================================================
# 4. ASYNCHRONOUS TEMPLATER
# =============================================================================


class AsyncTemplateRenderer:
    """
    Asynchronous template engine supporting Jinja-like variable interpolation,
    filters, conditional blocks, and domain-specific chemistry deck rendering.
    """

    _VAR_REGEX = re.compile(r"\{\{\s*(.*?)\s*\}\}")
    _BLOCK_IF_REGEX = re.compile(r"\{%\s*if\s+([a-zA-Z0-9_\.]+)\s*%\}(.*?)(?:\{%\s*else\s*%\}(.*?))?\{%\s*endif\s*%\}", re.DOTALL)

    async def render_async(self, template_str: str, context: Dict[str, Any]) -> str:
        """Asynchronously render template string with variable interpolation and conditional blocks."""
        # Yield to event loop to preserve async concurrency
        await asyncio.sleep(0)

        # 1. Process conditional blocks: {% if var %}...{% else %}...{% endif %}
        def _replace_if(match: re.Match[str]) -> str:
            var_name = match.group(1).strip()
            true_branch = match.group(2)
            false_branch = match.group(3) or ""
            val: Any = context
            for k in var_name.split("."):
                if isinstance(val, dict):
                    val = val.get(k)
                else:
                    val = None
                    break
            if val is None and var_name in context:
                val = context[var_name]
            if val:
                return true_branch
            return false_branch

        content = self._BLOCK_IF_REGEX.sub(_replace_if, template_str)

        # 2. Process variable placeholders: {{ key | filter }}
        def _replace_var(match: re.Match[str]) -> str:
            raw_expr = match.group(1).strip()
            if "|" in raw_expr:
                parts = [p.strip() for p in raw_expr.split("|", 1)]
                key = parts[0]
                filter_name = parts[1]
            else:
                key = raw_expr
                filter_name = ""

            # Resolve key (support nested dicts via dot notation)
            val: Any = context
            for k in key.split("."):
                if isinstance(val, dict):
                    val = val.get(k, "")
                else:
                    val = ""
                    break

            if val == "" and key in context:
                val = context[key]

            # Apply filters
            str_val = str(val) if val is not None else ""
            if filter_name == "upper":
                str_val = str_val.upper()
            elif filter_name == "lower":
                str_val = str_val.lower()
            elif filter_name.startswith("default("):
                default_match = re.match(r'default\([\'"]?(.*?)[\'"]?\)', filter_name)
                if default_match and (val is None or str_val == ""):
                    str_val = default_match.group(1)

            return str_val

        rendered = self._VAR_REGEX.sub(_replace_var, content)
        return rendered

    async def render_file_async(
        self,
        template_path: Union[str, Path],
        context: Dict[str, Any],
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Asynchronously load template from disk, render, and optionally write output."""
        tpl_path = resolve_mapped_path(template_path)
        if not tpl_path.is_file():
            raise FileNotFoundError(f"Template file not found: {tpl_path}")

        # Async file read
        loop = asyncio.get_running_loop()
        template_content = await loop.run_in_executor(None, tpl_path.read_text, "utf-8")

        rendered = await self.render_async(template_content, context)

        if output_path is not None:
            out_p = resolve_mapped_path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            await loop.run_in_executor(None, out_p.write_text, rendered, "utf-8")

        return rendered

    @staticmethod
    def build_orca_input_template(
        method: str,
        basis: str,
        charge: int = 0,
        multiplicity: int = 1,
        nprocs: int = 4,
        maxcore_mb: int = 3000,
        extra_keywords: str = "TightOpt TightSCF",
        coordinates_xyz: str = "",
    ) -> str:
        """Constructs an authoritative ORCA input deck adhering to Method Matrix §4.4."""
        return f"""! {method} {basis} {extra_keywords}
%pal nprocs {nprocs} end
%maxcore {maxcore_mb}
* xyz {charge} {multiplicity}
{coordinates_xyz.strip()}
*
"""

    @staticmethod
    def build_slurm_script_template(
        job_name: str,
        command: str,
        nodes: int = 1,
        cpus: int = 4,
        walltime: str = "24:00:00",
        partition: str = "compute",
        env_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """Constructs a standard SLURM batch submission script."""
        exports = ""
        if env_vars:
            exports = "\n".join(f"export {k}={v}" for k, v in env_vars.items()) + "\n"
        return f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={cpus}
#SBATCH --time={walltime}
#SBATCH --partition={partition}

{exports}srun --mpi=pmi2 {command}
"""

    @staticmethod
    def build_pbs_script_template(
        job_name: str,
        command: str,
        nodes: int = 1,
        cpus: int = 4,
        walltime: str = "24:00:00",
        env_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """Constructs a standard PBS batch submission script."""
        exports = ""
        if env_vars:
            exports = "\n".join(f"export {k}={v}" for k, v in env_vars.items()) + "\n"
        return f"""#!/bin/bash
#PBS -N {job_name}
#PBS -l nodes={nodes}:ppn={cpus}
#PBS -l walltime={walltime}

{exports}mpirun -np {nodes * cpus} {command}
"""

    @staticmethod
    def build_local_script_template(
        command: str,
        cpus: int = 4,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """Constructs a local shell execution script."""
        exports = ""
        if env_vars:
            exports = "\n".join(f"export {k}={v}" for k, v in env_vars.items()) + "\n"
        return f"""#!/bin/bash
{exports}{command}
"""


# =============================================================================
# 5. EXECUTION HANDSHAKE MANAGER
# =============================================================================


class ExecutionHandshakeManager:
    """
    Manages cryptographic execution handshakes, parameter hashing, and HMAC-SHA256 signatures
    to guarantee provenance integrity between compiler and execution sandbox.
    """

    def __init__(self, secret_key: Optional[str] = None) -> None:
        env_key = os.environ.get("COCHEM_SECRET_KEY")
        self.secret_key: str = secret_key if secret_key is not None else (env_key if env_key is not None else "cochem_master_secret_2026")

    def generate_handshake_token(
        self,
        job_id: str,
        config_payload: Dict[str, Any],
        secret_key: Optional[str] = None,
        ttl_seconds: int = 3600,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HandshakeToken:
        """Generates an HMAC-SHA256 signed HandshakeToken."""
        effective_key = secret_key or self.secret_key or "cochem_master_secret_2026"
        key = effective_key.encode("utf-8")
        issued_at = time.time()
        expires_at = issued_at + float(ttl_seconds)
        token_id = str(uuid.uuid4())
        nonce = secrets.token_hex(16)

        # Deterministic SHA-256 payload digest
        payload_str = json.dumps(config_payload, sort_keys=True)
        config_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        # Sign canonical token message
        message = f"{token_id}:{job_id}:{config_hash}:{issued_at:.4f}:{expires_at:.4f}:{nonce}"
        signature = hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()

        return HandshakeToken(
            token_id=token_id,
            job_id=job_id,
            config_hash=config_hash,
            signature=signature,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
            metadata=metadata or {},
        )

    def verify_handshake_token(
        self,
        token: Union[HandshakeToken, Dict[str, Any]],
        config_payload: Dict[str, Any],
        secret_key: Optional[str] = None,
        current_time: Optional[float] = None,
    ) -> HandshakeVerificationResult:
        """Verifies cryptographic token signature, hash integrity, and TTL expiration."""
        if isinstance(token, dict):
            t = HandshakeToken(**token)
        else:
            t = token

        now = current_time if current_time is not None else time.time()
        effective_key = secret_key or self.secret_key or "cochem_master_secret_2026"
        key = effective_key.encode("utf-8")

        # 1. Check TTL Expiration
        if now > t.expires_at:
            return HandshakeVerificationResult(
                is_valid=False,
                token_id=t.token_id,
                job_id=t.job_id,
                reason=f"Handshake token expired at {t.expires_at:.2f} (current: {now:.2f})",
                expired=True,
                signature_valid=False,
                hash_valid=False,
            )

        # 2. Check Payload SHA-256 Hash
        payload_str = json.dumps(config_payload, sort_keys=True)
        computed_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        hash_valid = hmac.compare_digest(computed_hash, t.config_hash)

        if not hash_valid:
            return HandshakeVerificationResult(
                is_valid=False,
                token_id=t.token_id,
                job_id=t.job_id,
                reason="Configuration payload hash mismatch.",
                expired=False,
                signature_valid=False,
                hash_valid=False,
            )

        # 3. Verify HMAC-SHA256 Signature
        message = f"{t.token_id}:{t.job_id}:{t.config_hash}:{t.issued_at:.4f}:{t.expires_at:.4f}:{t.nonce}"
        expected_sig = hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()
        sig_valid = hmac.compare_digest(expected_sig, t.signature)

        if not sig_valid:
            return HandshakeVerificationResult(
                is_valid=False,
                token_id=t.token_id,
                job_id=t.job_id,
                reason="Cryptographic HMAC signature verification failed.",
                expired=False,
                signature_valid=False,
                hash_valid=True,
            )

        return HandshakeVerificationResult(
            is_valid=True,
            token_id=t.token_id,
            job_id=t.job_id,
            reason="Handshake token successfully verified.",
            expired=False,
            signature_valid=True,
            hash_valid=True,
        )

    async def execute_handshake_session(
        self,
        job_id: str,
        config_payload: Dict[str, Any],
        runner_callback: Callable[[HandshakeToken], Awaitable[Dict[str, Any]]],
        secret_key: Optional[str] = None,
        ttl_seconds: int = 3600,
    ) -> Dict[str, Any]:
        """Runs an end-to-end async execution handshake session."""
        token = self.generate_handshake_token(job_id, config_payload, secret_key=secret_key, ttl_seconds=ttl_seconds)
        verification = self.verify_handshake_token(token, config_payload, secret_key=secret_key)
        if not verification.is_valid:
            raise HandshakeVerificationError(f"Session handshake failed: {verification.reason}")

        result = await runner_callback(token)
        result["handshake_verification"] = verification.model_dump()
        return result


# =============================================================================
# 6. ABSTRACTED HPC SCHEDULER STRATEGIES
# =============================================================================


class SchedulerStrategy(ABC):
    @abstractmethod
    def build_submission_script(self, job_name: str, command: str, nodes: int, cpus: int, **kwargs: Any) -> str:
        """Abstract method for rendering HPC submission scripts."""
        ...


class SlurmStrategy(SchedulerStrategy):
    def __init__(self, walltime: str = "24:00:00", partition: str = "compute") -> None:
        self.walltime = walltime
        self.partition = partition

    def build_submission_script(
        self,
        job_name: str,
        command: str,
        nodes: int,
        cpus: int,
        walltime: Optional[str] = None,
        partition: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> str:
        wtime = walltime or self.walltime
        part = partition or self.partition

        exports = ""
        if env_vars:
            exports = "\n".join(f"export {k}={v}" for k, v in env_vars.items()) + "\n"
        else:
            exports = f"export OMP_NUM_THREADS={cpus}\nexport MKL_NUM_THREADS={cpus}\n"

        return f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={cpus}
#SBATCH --time={wtime}
#SBATCH --partition={part}

{exports}srun --mpi=pmi2 {command}
"""


class PBSStrategy(SchedulerStrategy):
    def __init__(self, walltime: str = "24:00:00") -> None:
        self.walltime = walltime

    def build_submission_script(
        self,
        job_name: str,
        command: str,
        nodes: int,
        cpus: int,
        walltime: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> str:
        wtime = walltime or self.walltime

        exports = ""
        if env_vars:
            exports = "\n".join(f"export {k}={v}" for k, v in env_vars.items()) + "\n"
        else:
            exports = f"export OMP_NUM_THREADS={cpus}\nexport MKL_NUM_THREADS={cpus}\n"

        return f"""#!/bin/bash
#PBS -N {job_name}
#PBS -l nodes={nodes}:ppn={cpus}
#PBS -l walltime={wtime}

{exports}mpirun -np {nodes * cpus} {command}
"""


class LocalStrategy(SchedulerStrategy):
    def build_submission_script(
        self,
        job_name: str,
        command: str,
        nodes: int,
        cpus: int,
        env_vars: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> str:
        exports = ""
        if env_vars:
            exports = "\n".join(f"export {k}={v}" for k, v in env_vars.items()) + "\n"
        else:
            exports = f"export OMP_NUM_THREADS={cpus}\nexport MKL_NUM_THREADS={cpus}\n"

        return f"""#!/bin/bash
{exports}{command}
"""


# =============================================================================
# 7. MAIN CONFIG COMPILER CLASS
# =============================================================================


class ConfigCompiler:
    """
    CoChem Central Configuration Compiler & Execution Orchestrator.
    Combines SemVer gates, Mendeleev ECP validation, Dynamic Fallback Routing,
    Hardware-tailored environment synthesis, and Cryptographic Handshake tokens.
    """

    def __init__(
        self,
        target_scheduler: str = "local",
        walltime: str = "24:00:00",
        partition: str = "compute",
        secret_key: Optional[str] = None,
        hardware_profile: Optional[Union[HardwareProfileSpec, Dict[str, Any]]] = None,
        silo_verifier: Optional[MicroSiloVerifier] = None,
    ) -> None:
        self.target_scheduler = target_scheduler.lower()
        self.walltime = walltime
        self.partition = partition

        # Initialize Scheduler Strategy
        if self.target_scheduler == "slurm":
            self.scheduler: SchedulerStrategy = SlurmStrategy(walltime=walltime, partition=partition)
        elif self.target_scheduler == "pbs":
            self.scheduler = PBSStrategy(walltime=walltime)
        else:
            self.scheduler = LocalStrategy()

        # Initialize Hardware Profile
        if hardware_profile is not None:
            if isinstance(hardware_profile, dict):
                self.hardware = HardwareProfileSpec(**hardware_profile)
            else:
                self.hardware = hardware_profile
        else:
            self.hardware = HardwareProfileSpec.from_system()

        # Core Components
        self.router = DynamicFallbackRouter()
        self.verifier: Optional[MicroSiloVerifier] = silo_verifier
        self.templater = AsyncTemplateRenderer()
        self.handshake = ExecutionHandshakeManager(secret_key=secret_key)
        self.env_generator = HardwareEnvGenerator()

    def enforce_semver_pinning(self, engine_name: str, actual_version: str, min_required: str) -> bool:
        """Strict Semantic Versioning Gatekeeper."""
        if not actual_version:
            logger.error(f"Version string is empty or missing for dependency {engine_name}.")
            raise ValueError(f"Version string is empty or missing for dependency {engine_name}")

        if version.parse(actual_version) < version.parse(min_required):
            logger.error(f"{engine_name} version {actual_version} is below strict minimum {min_required}.")
            return False
        return True

    def validate_ecp_requirements(self, elements_in_system: List[str], defined_ecps: Dict[str, str]) -> None:
        """
        Dynamically queries Mendeleev to enforce Effective Core Potentials (ECPs)
        for any heavy element (Z > 36) to prevent massive basis set errors.
        """
        for sym in set(elements_in_system):
            try:
                el = element(sym)
                atomic_num = el.atomic_number
            except Exception as e:
                raise ValueError(f"Invalid chemical symbol '{sym}' encountered during ECP validation.") from e

            if atomic_num > 36 and sym not in defined_ecps:
                raise ECPValidationError(f"Heavy element {sym} (Z={atomic_num}) missing ECP specification")

    def generate_execution_package(
        self,
        job_name: str,
        engine_command: str,
        params: Dict[str, Any],
        nodes: int = 1,
        cpus: int = 4,
        walltime: Optional[str] = None,
        partition: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Tuple[str, str]:
        """
        Immutable SHA-256 Parameter Hashing & Scheduler Injection.
        Retains full backward compatibility with previous ConfigCompiler API.
        """
        param_str = json.dumps(params, sort_keys=True)
        config_hash = hashlib.sha256(param_str.encode()).hexdigest()

        script_body = self.scheduler.build_submission_script(
            job_name,
            engine_command,
            nodes,
            cpus,
            walltime=walltime,
            partition=partition,
            env_vars=env_vars,
            **kwargs,
        )
        provenance_header = f"\n# COCHEM_EXEC_HASH: {config_hash}\n"

        full_script = provenance_header + script_body
        logger.info(f"Compiled execution package for job '{job_name}' with SHA-256 hash: {config_hash[:12]}")

        return config_hash, full_script

    def compile_execution_bundle(
        self,
        job_name: str,
        requested_engine: str,
        params: Dict[str, Any],
        command_override: Optional[str] = None,
        task_type: Union[TaskType, str] = TaskType.CPU_BOUND,
        task_constraints: Optional[Dict[str, Any]] = None,
        nodes: int = 1,
        cpus: Optional[int] = None,
        walltime: Optional[str] = None,
        partition: Optional[str] = None,
        input_deck: Optional[str] = None,
    ) -> CompiledJobBundle:
        """
        Full zero-mock compilation pipeline:
        1. Resolves dynamic engine fallback.
        2. Synthesizes tailored hardware environment.
        3. Generates cryptographic handshake token.
        4. Renders scheduler script with provenance header.
        """
        # 1. Resolve fallback route
        decision = self.router.resolve_route(
            requested_engine=requested_engine,
            hardware=self.hardware,
            silo_verifier=self.verifier,
            task_constraints=task_constraints,
            task_type=task_type,
        )

        effective_cpus = cpus or decision.allocated_threads
        exec_cmd = command_override or decision.binary_path or f"{decision.selected_engine} input.inp"

        # 2. Generate Handshake Token
        handshake_token = self.handshake.generate_handshake_token(
            job_id=job_name,
            config_payload=params,
            metadata={"engine": decision.selected_engine, "task_type": str(task_type)},
        )

        # 3. Generate Execution Script
        config_hash, full_script = self.generate_execution_package(
            job_name=job_name,
            engine_command=exec_cmd,
            params=params,
            nodes=nodes,
            cpus=effective_cpus,
            walltime=walltime or self.walltime,
            partition=partition or self.partition,
            env_vars=decision.environment_variables,
        )

        provenance_header = f"# COCHEM_EXEC_HASH: {config_hash}\n# TOKEN_ID: {handshake_token.token_id}\n"

        return CompiledJobBundle(
            job_name=job_name,
            config_hash=config_hash,
            handshake_token=handshake_token,
            route_decision=decision,
            submission_script=full_script,
            input_deck=input_deck,
            environment_variables=decision.environment_variables,
            provenance_header=provenance_header,
        )

    async def compile_job_async(
        self,
        job_name: str,
        requested_engine: str,
        params: Dict[str, Any],
        command_override: Optional[str] = None,
        task_type: Union[TaskType, str] = TaskType.CPU_BOUND,
        task_constraints: Optional[Dict[str, Any]] = None,
        nodes: int = 1,
        cpus: Optional[int] = None,
        walltime: Optional[str] = None,
        partition: Optional[str] = None,
        input_deck_template: Optional[str] = None,
        deck_context: Optional[Dict[str, Any]] = None,
    ) -> CompiledJobBundle:
        """Asynchronously compiles an execution package with template rendering."""
        rendered_deck: Optional[str] = None
        if input_deck_template:
            ctx = deck_context or {}
            rendered_deck = await self.templater.render_async(input_deck_template, ctx)

        loop = asyncio.get_running_loop()
        bundle = await loop.run_in_executor(
            None,
            self.compile_execution_bundle,
            job_name,
            requested_engine,
            params,
            command_override,
            task_type,
            task_constraints,
            nodes,
            cpus,
            walltime,
            partition,
            rendered_deck,
        )
        return bundle


if __name__ == "__main__":
    compiler = ConfigCompiler(target_scheduler="slurm", walltime="12:00:00", partition="gpu")

    compiler.enforce_semver_pinning("ORCA", "6.1.1", "6.1.0")

    try:
        compiler.validate_ecp_requirements(["C", "H", "I"], defined_ecps={"I": "def2-TZVPP-ECP"})
        logger.info("ECP Validation Success")
    except ECPValidationError as e:
        logger.error(f"ECP Validation error: {e}")

    logger.info("Config Compiler initialized successfully.")
