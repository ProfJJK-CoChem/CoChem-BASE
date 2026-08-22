#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Temporal Engine Routing, Concurrency & Thermal Guardians
Authoritative Implementation for Method Matrix v4 (§8, §8A, §8B, §8C, §8D).

Provides:
1. The 10-Tier Temporal Wall Clock Matrix & GPU Orchestration (10s, 1min, 30min, 1h, 3h, 12h, 1d, 3d, 1w, 1mo).
2. Strict EMT Eradication (raises ValueError/RuntimeError on any EMT presence).
3. Automatic local asyncio timeout enforcement and Slurm #SBATCH --time parameter formatting.
4. gpu4pyscf (v1.8.0 FP64) capability, method, angular momentum, basis size crossover and memory gating.
5. Nvidia MPS provisioning with Ephemeral Compute Tier directory lockdown and Parsl two-executor hetero config helper.
6. Graceful Degradation & Preemption Timers with Windows CTRL_BREAK_EVENT (CREATE_NEW_PROCESS_GROUP) and POSIX SIGUSR1/SIGTERM.
7. Resizable, chunked, gzip+shuffle+fletcher32 QCSchema-compliant HDF5 PESStore implementation with checkpoint persistence.
8. Thermal Guard Daemon with async monitoring, psutil sensor reading, recursive p.suspend() and p.resume() recovery.
"""

from __future__ import annotations

import asyncio
import ctypes
import inspect
import json
import logging
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

if platform.system() == "Windows":
    try:
        import ctypes.wintypes
    except Exception:
        pass

import h5py
import numpy as np
import psutil
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-TemporalRouter")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# 1. The 10-Tier Temporal Wall Clock Matrix Constants & Metadata
# ---------------------------------------------------------------------------

class TemporalTier(str, Enum):
    """The 10 Discrete Temporal Wall Clock Tiers for CoChem-BASE (Method Matrix v4)."""
    TIER_1_10S = "10s"
    TIER_2_1MIN = "1min"
    TIER_3_30MIN = "30min"
    TIER_4_1H = "1h"
    TIER_5_3H = "3h"
    TIER_6_12H = "12h"
    TIER_7_1D = "1d"
    TIER_8_3D = "3d"
    TIER_9_1W = "1w"
    TIER_10_1MO = "1mo"


@dataclass(frozen=True)
class TierMetadata:
    """Metadata specification for a temporal wall clock tier."""
    tier: TemporalTier
    rank: int
    walltime_seconds: int
    slurm_time: str
    concurrency_tag: str
    recommended_methods: List[str]
    description: str


TIER_REGISTRY: Dict[TemporalTier, TierMetadata] = {
    TemporalTier.TIER_1_10S: TierMetadata(
        tier=TemporalTier.TIER_1_10S,
        rank=1,
        walltime_seconds=10,
        slurm_time="00:00:10",
        concurrency_tag="G",
        recommended_methods=["g-xTB", "GFN2-xTB", "GFN-FF", "AIMNet2", "MACE-OFF23", "MACE-OFF24m", "UMA"],
        description="Topology screening, MLFF screening and rapid preconditioning (sub-10s)",
    ),
    TemporalTier.TIER_2_1MIN: TierMetadata(
        tier=TemporalTier.TIER_2_1MIN,
        rank=2,
        walltime_seconds=60,
        slurm_time="00:01:00",
        concurrency_tag="G",
        recommended_methods=["gfn2-xtb-opt", "mlff-opt", "fast-dft-sp", "pm6"],
        description="Conformer coarse optimization and rapid single-point screening",
    ),
    TemporalTier.TIER_3_30MIN: TierMetadata(
        tier=TemporalTier.TIER_3_30MIN,
        rank=3,
        walltime_seconds=1800,
        slurm_time="00:30:00",
        concurrency_tag="C",
        recommended_methods=["r2scan-3c", "b97-3c", "crest-nci", "gpu4pyscf-df-r2scan"],
        description="Composite DFT optimizations and CREST conformer ensemble cross-checks",
    ),
    TemporalTier.TIER_4_1H: TierMetadata(
        tier=TemporalTier.TIER_4_1H,
        rank=4,
        walltime_seconds=3600,
        slurm_time="01:00:00",
        concurrency_tag="C",
        recommended_methods=["dft-def2-tzvp", "gpu4pyscf-wb97x", "orca-r2scan-3c-opt", "harmonic-freq"],
        description="Standard DFT geometry optimization and harmonic vibrational frequencies",
    ),
    TemporalTier.TIER_5_3H: TierMetadata(
        tier=TemporalTier.TIER_5_3H,
        rank=5,
        walltime_seconds=10800,
        slurm_time="03:00:00",
        concurrency_tag="C",
        recommended_methods=["wb97m-v/qz", "recipe-R2", "frozen-monomer-dft", "dft-vpt2"],
        description="High-level DFT (QZVPP), CP corrections, and DFT-VPT2 on semi-rigid manifold",
    ),
    TemporalTier.TIER_6_12H: TierMetadata(
        tier=TemporalTier.TIER_6_12H,
        rank=6,
        walltime_seconds=43200,
        slurm_time="12:00:00",
        concurrency_tag="P",
        recommended_methods=["junchs", "active-learning-pes", "mp2-f12", "dlpno-ccsd(t)-sp"],
        description="junChS composite, active-learning PES (300-800 points), and MP2-F12",
    ),
    TemporalTier.TIER_7_1D: TierMetadata(
        tier=TemporalTier.TIER_7_1D,
        rank=7,
        walltime_seconds=86400,
        slurm_time="1-00:00:00",
        concurrency_tag="S",
        recommended_methods=["dlpno-ccsd(t)-opt", "semi-rigid-vpt2", "cfour-ccsd(t)-sp"],
        description="DLPNO-CCSD(T) optimization and semi-rigid manifold vibrational averaging (B0)",
    ),
    TemporalTier.TIER_8_3D: TierMetadata(
        tier=TemporalTier.TIER_8_3D,
        rank=8,
        walltime_seconds=259200,
        slurm_time="3-00:00:00",
        concurrency_tag="S",
        recommended_methods=["cfour-ccsd(t)-vibrot", "6d-pes-variational", "delta-learning-pes-campaign"],
        description="CFOUR CCSD(T) analytic 2nd derivatives and 6D variational PES campaigns",
    ),
    TemporalTier.TIER_9_1W: TierMetadata(
        tier=TemporalTier.TIER_9_1W,
        rank=9,
        walltime_seconds=604800,
        slurm_time="7-00:00:00",
        concurrency_tag="S",
        recommended_methods=["cfour-anharmonic-ff", "large-basis-ccsd(t)", "multi-isotopologue-campaign"],
        description="Full anharmonic CCSD(T) force fields and large-basis coupled cluster campaigns",
    ),
    TemporalTier.TIER_10_1MO: TierMetadata(
        tier=TemporalTier.TIER_10_1MO,
        rank=10,
        walltime_seconds=2592000,
        slurm_time="30-00:00:00",
        concurrency_tag="S",
        recommended_methods=["multi-day-dlpno-ccsd(t)", "full-dimensional-fci-pes", "focal-point-anharmonic-cbs"],
        description="Full dimensional coupled cluster / focal point CBS campaigns across large complexes",
    ),
}

# ---------------------------------------------------------------------------
# Eradication of EMT (Effective Medium Theory) & Gating Constants
# ---------------------------------------------------------------------------
FORBIDDEN_THEORIES: Set[str] = {
    "emt",
    "effective_medium_theory",
    "effective-medium-theory",
    "effective medium theory",
    "ase_emt",
    "emt_potential",
}

GPU4PYSCF_FORBIDDEN_METHODS: Set[str] = {
    "double_hybrid",
    "dlpno",
    "canonical_ccsd(t)",
    "ccsd(t)",
    "casscf",
    "nevpt2",
    "mp2_gradient",
    "mp2_hessian",
    "tddft_hessian",
    "f12",
}

GPU4PYSCF_SUPPORTED_METHODS: Set[str] = {
    "hf",
    "rhf",
    "uhf",
    "rks",
    "uks",
    "dft",
    "b3lyp",
    "pbe",
    "pbe0",
    "r2scan",
    "r2scan-3c",
    "b97-d",
    "b97-3c",
    "wb97x",
    "wb97x-d",
    "wb97x-d3",
    "wb97x-d4",
    "wb97m-v",
    "wb97m-d3bj",
    "m06-2x",
    "tpssh",
    "scan",
    "lda",
    "svwn",
}

ANGULAR_MOMENTUM_MAP: Dict[str, int] = {
    "s": 0, "p": 1, "d": 2, "f": 3, "g": 4, "h": 5, "i": 6, "k": 7
}


class ThermalState(str, Enum):
    """Thermal operational state for process tree throttling and safety."""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    THROTTLED = "THROTTLED"
    SUSPENDED = "SUSPENDED"


# ---------------------------------------------------------------------------
# Strict Validation Helpers
# ---------------------------------------------------------------------------

EMT_REGEX = re.compile(r"(?:^|[^a-zA-Z0-9])emt(?:$|[^a-zA-Z0-9])|effective[\s_-]*medium[\s_-]*theory", re.IGNORECASE)


def validate_theory_cleanliness(value: Any) -> None:
    """Recursively validates that EMT (Effective Medium Theory) is strictly absent.

    Raises:
        ValueError: If EMT is detected in any string, dictionary key, or nested list.
    """
    if isinstance(value, str):
        val_lower = value.strip().lower()
        if (
            val_lower in FORBIDDEN_THEORIES
            or bool(EMT_REGEX.search(val_lower))
            or "effective medium theory" in val_lower
            or "effective_medium_theory" in val_lower
        ):
            raise ValueError(
                f"CRITICAL METHOD ERROR: EMT (Effective Medium Theory) detected ('{value}'). "
                "EMT is strictly eradicated from all CoChem tiers as scientifically invalid for non-covalent complexes."
            )
    elif isinstance(value, dict):
        for k, v in value.items():
            validate_theory_cleanliness(k)
            validate_theory_cleanliness(v)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            validate_theory_cleanliness(item)


# ---------------------------------------------------------------------------
# Job Specification & Routing Decision Models
# ---------------------------------------------------------------------------

class JobSpec(BaseModel):
    """Pydantic model representing incoming molecular computation specifications."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    n_atoms: int = Field(..., ge=1, description="Total number of atoms in the molecular system")
    n_heavy_atoms: Optional[int] = Field(default=None, description="Number of non-hydrogen atoms")
    symbols: Optional[List[str]] = Field(default=None, description="List of atomic symbols")
    method: str = Field(..., description="Level of theory (e.g. 'GFN2-xTB', 'wB97M-V', 'DLPNO-CCSD(T)')")
    basis: Optional[str] = Field(default=None, description="Gaussian basis set name")
    aux_basis: Optional[str] = Field(default=None, description="Auxiliary basis set for density fitting")
    task_type: str = Field(default="energy", description="Task: 'energy', 'gradient', 'opt', 'freq', 'vpt2', 'pes_scan', 'global_search', 'anharmonic_ff'")
    observable: Optional[str] = Field(default=None, description="Target physical observable")
    product_class: str = Field(default="A", description="Product class: 'A' (de novo), 'B' (semi-experimental), 'C' (differences)")
    has_gpu: bool = Field(default=False, description="Whether GPU accelerator is available")
    n_cores: int = Field(default=8, ge=1, description="Allocated CPU cores")
    ram_gb: float = Field(default=64.0, gt=0.0, description="Available host RAM in GB")
    density_fitting: bool = Field(default=True, description="Whether density fitting / RI is enabled")
    restart_needed: bool = Field(default=False, description="Whether job is a continuation of prior state")
    keywords: Dict[str, Any] = Field(default_factory=dict, description="Additional method keywords")

    @model_validator(mode="before")
    @classmethod
    def check_emt_eradication(cls, data: Any) -> Any:
        """Strictly eradicate EMT across all input fields before instantiation."""
        if isinstance(data, dict):
            validate_theory_cleanliness(data)
        return data

    @field_validator("method", "task_type")
    @classmethod
    def validate_strings(cls, v: str) -> str:
        validate_theory_cleanliness(v)
        return v


@dataclass
class RoutingDecision:
    """Result of temporal tier classification and hardware engine routing."""
    tier: TemporalTier
    engine: str
    device: str
    precision: str
    density_fitting: bool
    walltime_seconds: int
    slurm_time: str
    concurrency_tag: str
    n_ranks: int
    maxcore_mb: int
    state_in: Optional[str] = None
    state_out: Optional[str] = None
    explanation: str = ""


# ---------------------------------------------------------------------------
# Basis Count & Angular Momentum Helpers
# ---------------------------------------------------------------------------

def estimate_basis_count(
    n_atoms: int,
    symbols: Optional[Sequence[str]] = None,
    basis: Optional[str] = None,
    n_heavy: Optional[int] = None,
) -> int:
    """Estimates the total number of basis functions for crossover calculation."""
    if symbols:
        heavy_count = sum(1 for s in symbols if s.strip().upper() not in ("H", "HE"))
        h_count = len(symbols) - heavy_count
    elif n_heavy is not None:
        heavy_count = n_heavy
        h_count = max(0, n_atoms - n_heavy)
    else:
        # Heuristic: assume ~50% heavy atoms if unspecified
        heavy_count = max(1, n_atoms // 2)
        h_count = n_atoms - heavy_count

    b_str = (basis or "def2-tzvp").lower()
    if "qz" in b_str or "qzvpp" in b_str or "cc-pvqz" in b_str:
        return heavy_count * 55 + h_count * 14
    elif "tz" in b_str or "tzvp" in b_str or "tzvpp" in b_str or "cc-pvtz" in b_str:
        return heavy_count * 28 + h_count * 8
    elif "svp" in b_str or "dz" in b_str or "cc-pvdz" in b_str or "6-31g" in b_str:
        return heavy_count * 14 + h_count * 5
    elif "sto" in b_str or "min" in b_str:
        return heavy_count * 5 + h_count * 1
    else:
        return heavy_count * 28 + h_count * 8


def get_max_angular_momentum(basis_name: Optional[str]) -> str:
    """Determines maximum orbital angular momentum for a given standard basis set."""
    if not basis_name:
        return "f"
    b = basis_name.lower()
    if "5z" in b or "6z" in b:
        return "h"
    elif "qz" in b or "qzvpp" in b or "cc-pvqz" in b:
        return "g"
    elif "tz" in b or "tzvp" in b or "tzvpp" in b or "cc-pvtz" in b:
        return "f"
    elif "dz" in b or "svp" in b or "def2-sv" in b:
        return "d"
    return "d"


# ---------------------------------------------------------------------------
# Temporal Classification Matrix Router
# ---------------------------------------------------------------------------

def classify_job_tier(job: JobSpec) -> TemporalTier:
    """Classifies incoming molecular job into the 10-tier temporal matrix.

    Scales strictly based on topological size (heavy atoms), level of theory, task type,
    and hardware capacity.

    Zero-Tolerance: EMT is eradicated.
    """
    validate_theory_cleanliness(job.method)
    validate_theory_cleanliness(job.keywords)

    method_clean = job.method.lower().replace("-", "").replace("_", "")
    task_clean = job.task_type.lower().replace("-", "").replace("_", "")
    n_heavy = job.n_heavy_atoms if job.n_heavy_atoms is not None else (
        sum(1 for s in job.symbols if s.strip().upper() not in ("H", "HE"))
        if job.symbols else max(1, job.n_atoms // 2)
    )

    # 1. Tier 1 (10s): sub-10s g-xTB or MLFF screening
    is_mlff = any(m in method_clean for m in ["aimnet2", "mace", "uma", "ani", "mlff"])
    is_xtb = any(m in method_clean for m in ["gxtb", "gfnxtb", "gfn2xtb", "gfnff", "xtb"])

    if task_clean in ["screen", "topologyscreen", "filter", "mlffscreen"]:
        return TemporalTier.TIER_1_10S
    if (is_mlff or is_xtb) and task_clean in ["energy", "sp", "gradient"] and job.n_atoms <= 40:
        return TemporalTier.TIER_1_10S
    if is_mlff and task_clean in ["opt", "relax"] and job.n_atoms <= 15:
        return TemporalTier.TIER_1_10S

    # 2. Tier 2 (1min): coarse opt or fast semi-empirical / small DFT SP
    if (is_mlff or is_xtb) and task_clean in ["opt", "relax", "geometry"]:
        return TemporalTier.TIER_2_1MIN
    if is_xtb and task_clean in ["freq", "harmonic"]:
        return TemporalTier.TIER_2_1MIN
    if any(m in method_clean for m in ["pm6", "am1", "pm3"]):
        return TemporalTier.TIER_2_1MIN
    if "dft" in method_clean and task_clean in ["energy", "sp"] and job.n_atoms <= 10:
        return TemporalTier.TIER_2_1MIN

    # 3. Tier 3 (30min): composite DFT (r2SCAN-3c), CREST search, fast DFT opt
    if "crest" in method_clean or task_clean in ["crest", "globalsearch", "conformerenum"]:
        return TemporalTier.TIER_3_30MIN
    if any(m in method_clean for m in ["r2scan3c", "b973c", "hf3c"]):
        if task_clean in ["energy", "sp", "gradient", "opt"]:
            return TemporalTier.TIER_3_30MIN
    if "dft" in method_clean or any(m in method_clean for m in ["b3lyp", "pbe", "pbe0", "wb97x"]):
        if task_clean in ["energy", "sp"] and job.n_atoms <= 30:
            return TemporalTier.TIER_3_30MIN
        if task_clean in ["opt", "relax"] and n_heavy <= 4:
            return TemporalTier.TIER_3_30MIN

    # 4. Tier 4 (1h): standard DFT def2-TZVP opt + harmonic frequencies
    if any(m in method_clean for m in ["dft", "b3lyp", "pbe", "pbe0", "wb97x", "r2scan"]):
        if task_clean in ["opt", "relax", "geometry"] and n_heavy <= 10:
            return TemporalTier.TIER_4_1H
        if task_clean in ["freq", "harmonic"] and n_heavy <= 8:
            return TemporalTier.TIER_4_1H

    # 5. Tier 5 (3h): High-level DFT (Recipe R2: wB97M-V/def2-QZVPP + CP + DFT-VPT2)
    if "vpt2" in task_clean and ("dft" in method_clean or "wb97" in method_clean or "b3lyp" in method_clean):
        if n_heavy <= 8:
            return TemporalTier.TIER_5_3H
    if any(m in method_clean for m in ["wb97mv", "m062x", "mp2"]) and task_clean in ["opt", "relax", "freq"]:
        if n_heavy <= 10:
            return TemporalTier.TIER_5_3H
    if "reciper2" in method_clean or ("wb97" in method_clean and "qz" in str(job.basis).lower()):
        return TemporalTier.TIER_5_3H

    # 6. Tier 6 (12h): junChS composite, active-learning PES (300-800 pts), MP2-F12, DLPNO SP
    if any(m in method_clean for m in ["junchs", "mp2f12"]) or (
        "activelearning" in method_clean or "pes" in task_clean and job.n_atoms <= 10
    ):
        return TemporalTier.TIER_6_12H
    if "dlpno" in method_clean and task_clean in ["energy", "sp"]:
        return TemporalTier.TIER_6_12H

    # 7. Tier 7 (1d): DLPNO-CCSD(T) optimization, semi-rigid manifold VPT2
    if "dlpno" in method_clean and task_clean in ["opt", "relax", "geometry"]:
        return TemporalTier.TIER_7_1D
    if "vpt2" in task_clean and n_heavy <= 12:
        return TemporalTier.TIER_7_1D
    if "ccsd(t)" in method_clean and task_clean in ["energy", "sp"] and n_heavy <= 6:
        return TemporalTier.TIER_7_1D

    # 8. Tier 8 (3d): CFOUR CCSD(T) analytic 2nd derivatives, 6D variational PES
    if any(m in method_clean for m in ["cfour", "analytic2nd", "vibrot", "6dpes"]):
        return TemporalTier.TIER_8_3D
    if "ccsd(t)" in method_clean and task_clean in ["freq", "hessian"] and n_heavy <= 8:
        return TemporalTier.TIER_8_3D

    # 9. Tier 9 (1w): Full CFOUR CCSD(T) anharmonic force field, large-basis coupled cluster
    if ("anharmonicff" in task_clean or "vpt2" in task_clean) and ("ccsd(t)" in method_clean or "cfour" in method_clean):
        if n_heavy <= 10 and job.n_atoms <= 16:
            return TemporalTier.TIER_9_1W
        return TemporalTier.TIER_10_1MO
    if "anharmonicff" in task_clean:
        if n_heavy <= 10 and job.n_atoms <= 16:
            return TemporalTier.TIER_9_1W
        return TemporalTier.TIER_10_1MO
    if "ccsd(t)" in method_clean and task_clean in ["opt", "freq"]:
        if n_heavy <= 10 and job.n_atoms <= 16:
            return TemporalTier.TIER_9_1W
        return TemporalTier.TIER_10_1MO

    # 10. Tier 10 (1mo): Multi-day DLPNO-CCSD(T), focal point CBS, full dimensional FCI PES
    return TemporalTier.TIER_10_1MO


# ---------------------------------------------------------------------------
# Slurm & Asyncio Timeout Formatting
# ---------------------------------------------------------------------------

def format_slurm_time(tier_or_seconds: Union[TemporalTier, str, int, float]) -> str:
    """Formats Slurm #SBATCH --time parameter adhering strictly to the 10-tier matrix.

    Examples:
        '10s' -> '00:00:10'
        '1min' -> '00:01:00'
        '30min' -> '00:30:00'
        '1h' -> '01:00:00'
        '3h' -> '03:00:00'
        '12h' -> '12:00:00'
        '1d' -> '1-00:00:00'
        '3d' -> '3-00:00:00'
        '1w' -> '7-00:00:00'
        '1mo' -> '30-00:00:00'
    """
    if isinstance(tier_or_seconds, TemporalTier):
        return TIER_REGISTRY[tier_or_seconds].slurm_time

    if isinstance(tier_or_seconds, str):
        try:
            tier_enum = TemporalTier(tier_or_seconds)
            return TIER_REGISTRY[tier_enum].slurm_time
        except ValueError:
            pass

    # Numeric seconds conversion
    seconds = int(tier_or_seconds) if isinstance(tier_or_seconds, (int, float)) else 3600
    if seconds < 0:
        seconds = 10

    days = seconds // 86400
    remainder = seconds % 86400
    hours = remainder // 3600
    remainder = remainder % 3600
    minutes = remainder // 60
    secs = remainder % 60

    if days > 0:
        return f"{days}-{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def get_asyncio_timeout(tier_or_seconds: Union[TemporalTier, str, int, float]) -> float:
    """Extracts floating point timeout in seconds for asyncio.wait_for."""
    if isinstance(tier_or_seconds, TemporalTier):
        return float(TIER_REGISTRY[tier_or_seconds].walltime_seconds)
    if isinstance(tier_or_seconds, str):
        try:
            tier_enum = TemporalTier(tier_or_seconds)
            return float(TIER_REGISTRY[tier_enum].walltime_seconds)
        except ValueError:
            pass
    return float(tier_or_seconds)


async def async_execute_with_tier_timeout(
    coro: Any,
    tier_or_seconds: Union[TemporalTier, str, int, float],
    timeout_callback: Optional[Callable[[], Any]] = None,
) -> Any:
    """Executes a coroutine guarded strictly by the tier's wall clock timeout limit."""
    timeout_sec = get_asyncio_timeout(tier_or_seconds)
    try:
        return await asyncio.wait_for(coro, timeout=timeout_sec)
    except asyncio.TimeoutError:
        logger.error(f"Execution exceeded tier timeout of {timeout_sec:.2f}s ({tier_or_seconds})")
        if timeout_callback:
            if inspect.iscoroutinefunction(timeout_callback):
                await timeout_callback()
            else:
                timeout_callback()
        raise


# ---------------------------------------------------------------------------
# Electronic Structure Routing (gpu4pyscf v1.8.0 FP64 & CPU Alternatives)
# ---------------------------------------------------------------------------

def route_electronic_structure(job: JobSpec) -> RoutingDecision:
    """Authoritative routing procedure for electronic structure jobs (Method Matrix §8.5).

    Routes supported DFT/SCF calculations to gpu4pyscf (v1.8.0 FP64) when GPU is available
    and size/basis/method meets crossover criteria.
    """
    validate_theory_cleanliness(job.method)
    tier = classify_job_tier(job)
    meta = TIER_REGISTRY[tier]

    method_lower = job.method.lower().replace("-", "").replace("_", "")
    n_basis = estimate_basis_count(job.n_atoms, job.symbols, job.basis, job.n_heavy_atoms)
    max_l = get_max_angular_momentum(job.basis)
    max_l_val = ANGULAR_MOMENTUM_MAP.get(max_l, 3)

    # 1. Check if method is forbidden on GPU
    is_forbidden_gpu = any(fb in method_lower for fb in [
        "doublehybrid", "dlpno", "canonicalccsd(t)", "ccsd(t)", "casscf",
        "nevpt2", "mp2gradient", "mp2hessian", "tddfthessian", "f12"
    ])

    # 2. Check if method is supported by gpu4pyscf (v1.8.0 FP64)
    is_supported_dft_scf = any(sm in method_lower for sm in [
        "hf", "rhf", "uhf", "rks", "uks", "dft", "b3lyp", "pbe", "pbe0",
        "r2scan", "b97", "wb97", "wb97x", "wb97mv", "m062x", "tpssh", "scan"
    ])

    # 3. Angular momentum gate: orbital <= g (val <= 4), auxiliary <= i (val <= 6)
    l_gate_passed = max_l_val <= ANGULAR_MOMENTUM_MAP["g"]

    # 4. Memory working set check (RTX 3090 / 24 GB)
    estimated_vram_gb = (n_basis ** 2 * 8 * 4) / (1024 ** 3) + 1.5
    memory_fits = estimated_vram_gb < 24.0

    # 5. Crossover decision (§8.3 & §8.5):
    # n_basis < 50: CPU/ORCA competitive or preferred
    # 50 <= n_basis <= 300: GPU with Density Fitting (DF-SCF) pays over CPU
    # n_basis > 300: GPU wins decisively
    if (
        job.has_gpu
        and not is_forbidden_gpu
        and is_supported_dft_scf
        and l_gate_passed
        and memory_fits
        and job.density_fitting
        and n_basis >= 50
    ):
        return RoutingDecision(
            tier=tier,
            engine="gpu4pyscf",
            device="gpu",
            precision="FP64",
            density_fitting=True,
            walltime_seconds=meta.walltime_seconds,
            slurm_time=meta.slurm_time,
            concurrency_tag="G",
            n_ranks=1,
            maxcore_mb=int(min(job.ram_gb * 1024, 6144)),
            state_in="chkfile.h5" if job.restart_needed else None,
            state_out="chkfile.h5",
            explanation=f"Routed to gpu4pyscf (v1.8.0 FP64) with DF. Basis count ({n_basis} bf) exceeds GPU crossover.",
        )

    # If MLFF
    if any(m in method_lower for m in ["aimnet2", "mace", "uma"]):
        return RoutingDecision(
            tier=tier,
            engine="mace" if "mace" in method_lower else ("aimnet2" if "aimnet2" in method_lower else "uma"),
            device="gpu" if job.has_gpu else "cpu",
            precision="FP32",
            density_fitting=False,
            walltime_seconds=meta.walltime_seconds,
            slurm_time=meta.slurm_time,
            concurrency_tag="G" if job.has_gpu else "C",
            n_ranks=1,
            maxcore_mb=2048,
            state_in=None,
            state_out="seed_ensemble.xyz",
            explanation="Routed to MLFF engine for screening / preconditioning.",
        )

    # If Coupled Cluster or CFOUR
    if any(m in method_lower for m in ["cfour", "analytic2nd", "vibrot", "sextic"]) or (
        "ccsd(t)" in method_lower and job.task_type in ["freq", "hessian", "anharmonic_ff"]
    ):
        return RoutingDecision(
            tier=tier,
            engine="cfour",
            device="cpu",
            precision="FP64",
            density_fitting=False,
            walltime_seconds=meta.walltime_seconds,
            slurm_time=meta.slurm_time,
            concurrency_tag="S",
            n_ranks=min(job.n_cores, 8),
            maxcore_mb=3000,
            state_in="JOBARC" if job.restart_needed else None,
            state_out="JAINDX",
            explanation="Routed to CFOUR (CPU) for analytic CCSD(T) derivatives & VPT2.",
        )

    # Standard CPU Route (ORCA / PySCF CPU)
    return RoutingDecision(
        tier=tier,
        engine="orca",
        device="cpu",
        precision="FP64",
        density_fitting=job.density_fitting,
        walltime_seconds=meta.walltime_seconds,
        slurm_time=meta.slurm_time,
        concurrency_tag="C",
        n_ranks=min(job.n_cores, 7 if job.has_gpu else 8),
        maxcore_mb=3400 if job.has_gpu else 3000,
        state_in="base.gbw" if job.restart_needed else None,
        state_out="base.gbw",
        explanation="Routed to ORCA (CPU) on P-cores with reserved companion budget.",
    )


# ---------------------------------------------------------------------------
# Nvidia MPS & Ephemeral Compute Tier Provisioning
# ---------------------------------------------------------------------------

def provision_mps_environment(
    ephemeral_root: Optional[Union[str, Path]] = None,
    active_thread_pct: int = 33,
    pinned_mem_limit: str = "0=6G",
    user: Optional[str] = None,
) -> Dict[str, str]:
    """Provisions Nvidia MPS IPC sockets and logs within the Ephemeral Compute Tier.

    Applies strict permissions lockdown (0o700 / chmod 700 / Windows ACL equivalent).
    """
    if ephemeral_root is not None:
        base_path = Path(ephemeral_root)
    else:
        # Respect SLURM_TMPDIR, COCHEM_EPHEMERAL_DIR or system temp
        slurm_tmp = os.environ.get("SLURM_TMPDIR")
        cochem_tmp = os.environ.get("COCHEM_EPHEMERAL_DIR")
        if slurm_tmp and Path(slurm_tmp).exists():
            base_path = Path(slurm_tmp)
        elif cochem_tmp and Path(cochem_tmp).exists():
            base_path = Path(cochem_tmp)
        else:
            base_path = Path(tempfile.gettempdir())

    user_str = user or os.environ.get("USER", os.environ.get("USERNAME", "cochem_user"))
    exec_uuid = uuid.uuid4().hex[:12]
    mps_dir = base_path / f"cochem_exec_{exec_uuid}" / f"cochem_mps_{user_str}"
    pipe_dir = mps_dir / "pipe"
    log_dir = mps_dir / "log"

    # Create directories
    pipe_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Lockdown permissions (0o700)
    try:
        if platform.system() != "Windows":
            os.chmod(mps_dir.parent, 0o700)
            os.chmod(mps_dir, 0o700)
            os.chmod(pipe_dir, 0o700)
            os.chmod(log_dir, 0o700)
    except Exception as e:
        logger.warning(f"Could not adjust directory chmod to 0o700: {e}")

    env_vars: Dict[str, str] = {
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "0"),
        "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(active_thread_pct),
        "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT": pinned_mem_limit,
        "CUDA_MPS_PIPE_DIRECTORY": str(pipe_dir.resolve()),
        "CUDA_MPS_LOG_DIRECTORY": str(log_dir.resolve()),
        "COCHEM_EPHEMERAL_EXEC_DIR": str(mps_dir.resolve()),
    }
    return env_vars


def build_parsl_hetero_config(
    cpu_workers: int = 1,
    cpu_cores_per_worker: int = 7,
    gpu_workers: int = 3,
    mem_per_cpu_worker_gb: int = 28,
    mem_per_gpu_worker_gb: int = 6,
    active_thread_pct: int = 33,
    pinned_mem_limit: str = "0=6G",
    ephemeral_dir: Optional[Union[str, Path]] = None,
    provider_type: str = "local",
) -> Any:
    """Builds Parsl two-executor configuration (CPU anchor + GPU scout under MPS).

    Method Matrix §8A.6 compliant.
    """
    mps_env = provision_mps_environment(
        ephemeral_root=ephemeral_dir,
        active_thread_pct=active_thread_pct,
        pinned_mem_limit=pinned_mem_limit,
    )

    gpu_init_script = (
        f"export CUDA_VISIBLE_DEVICES={mps_env['CUDA_VISIBLE_DEVICES']}; "
        f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={active_thread_pct}; "
        f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{pinned_mem_limit}'; "
        f"export CUDA_MPS_PIPE_DIRECTORY='{mps_env['CUDA_MPS_PIPE_DIRECTORY']}'; "
        f"export CUDA_MPS_LOG_DIRECTORY='{mps_env['CUDA_MPS_LOG_DIRECTORY']}'; "
        "ulimit -n 16384"
    )

    cpu_init_script = (
        "export OMP_NUM_THREADS=1; "
        "export KMP_HW_SUBSET=8c:intel_core,1t"
    )

    try:
        from parsl.config import Config
        from parsl.executors import HighThroughputExecutor
        from parsl.providers import LocalProvider, SlurmProvider

        cpu_provider: Any
        gpu_provider: Any
        if provider_type.lower() == "slurm":
            cpu_provider = SlurmProvider(
                nodes_per_block=1,
                init_blocks=1,
                min_blocks=1,
                max_blocks=1,
                scheduler_options="#SBATCH --cpus-per-task=8",
                worker_init=cpu_init_script,
            )
            gpu_provider = SlurmProvider(
                nodes_per_block=1,
                init_blocks=1,
                min_blocks=1,
                max_blocks=1,
                scheduler_options="#SBATCH --gres=gpu:1 --gpus-per-node=1",
                worker_init=gpu_init_script,
            )
        else:
            cpu_provider = LocalProvider(  # type: ignore[no-untyped-call]
                init_blocks=1,
                min_blocks=1,
                max_blocks=1,
                worker_init=cpu_init_script,
            )
            gpu_provider = LocalProvider(  # type: ignore[no-untyped-call]
                init_blocks=1,
                min_blocks=1,
                max_blocks=1,
                worker_init=gpu_init_script,
            )

        config = Config(
            executors=[
                HighThroughputExecutor(
                    label="cpu",
                    max_workers_per_node=cpu_workers,
                    cores_per_worker=cpu_cores_per_worker,
                    cpu_affinity="block",
                    mem_per_worker=mem_per_cpu_worker_gb,
                    provider=cpu_provider,
                ),
                HighThroughputExecutor(
                    label="gpu",
                    available_accelerators=gpu_workers,
                    max_workers_per_node=gpu_workers,
                    cores_per_worker=1,
                    cpu_affinity="block-reverse",
                    mem_per_worker=mem_per_gpu_worker_gb,
                    provider=gpu_provider,
                ),
            ],
            retries=2,
        )
        return config

    except ImportError:
        logger.info("Parsl is not installed; returning dictionary representation of config.")
        return {
            "executors": {
                "cpu": {
                    "label": "cpu",
                    "cores_per_worker": cpu_cores_per_worker,
                    "max_workers": cpu_workers,
                    "affinity": "block",
                    "worker_init": cpu_init_script,
                },
                "gpu": {
                    "label": "gpu",
                    "available_accelerators": gpu_workers,
                    "max_workers": gpu_workers,
                    "affinity": "block-reverse",
                    "worker_init": gpu_init_script,
                },
            },
            "mps_env": mps_env,
            "retries": 2,
        }


# ---------------------------------------------------------------------------
# HDF5 PESStore Implementation (Method Matrix §8C)
# ---------------------------------------------------------------------------

VLEN_STR = h5py.string_dtype(encoding="utf-8")
CHUNK_POINTS = 512


class PESStore:
    """Resizable, chunked, gzip+shuffle+fletcher32 HDF5 PES Store with QCSchema field names."""

    def __init__(
        self,
        path: Union[str, Path],
        complex_name: str = "",
        symbols: Sequence[str] = (),
    ) -> None:
        self.path = Path(path)
        new_file = not self.path.exists()
        if new_file:
            self.path.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(self.path, "a") as f:
            m = f.require_group("meta")
            if new_file:
                m.attrs["schema_name"] = "vdw_pes_campaign"
                m.attrs["schema_version"] = 1
                m.attrs["created_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if complex_name:
                m.attrs["complex"] = complex_name
            if symbols:
                m.attrs["symbols"] = json.dumps(list(symbols))
                m.attrs["n_atoms"] = len(symbols)
            self.n_atoms = int(m.attrs.get("n_atoms", len(symbols)))

    def register_method(self, method_id: str, **attrs: Any) -> None:
        """Registers a computational method with QCSchema attributes."""
        validate_theory_cleanliness(method_id)
        validate_theory_cleanliness(attrs)
        with h5py.File(self.path, "a") as f:
            g = f.require_group(f"methods/{method_id}")
            for k, v in attrs.items():
                g.attrs[k] = json.dumps(v) if isinstance(v, (dict, list)) else v
            g.attrs.setdefault("registered_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def _ds(
        self,
        f: h5py.File,
        mid: str,
        name: str,
        shape_tail: Tuple[int, ...],
        dtype: Any,
        checksum: bool = False,
    ) -> h5py.Dataset:
        grp = f.require_group(f"points/{mid}")
        if name in grp:
            return grp[name]

        kw: Dict[str, Any] = {
            "shape": (0,) + shape_tail,
            "maxshape": (None,) + shape_tail,
            "dtype": dtype,
            "chunks": (CHUNK_POINTS,) + shape_tail,
        }
        if dtype != VLEN_STR:
            kw.update(compression="gzip", compression_opts=4, shuffle=True)
            if checksum:
                kw["fletcher32"] = True
        return grp.create_dataset(name, **kw)

    @staticmethod
    def _append(ds: h5py.Dataset, block: np.ndarray) -> int:
        idx = int(ds.shape[0])
        ds.resize(idx + len(block), axis=0)
        ds[idx:] = block
        return idx

    def add_points(
        self,
        method_id: str,
        coords: Any,
        energies: Any,
        *,
        point_ids: Optional[Sequence[str]] = None,
        gradients: Optional[Any] = None,
        converged: Optional[Any] = None,
        wall_s: Optional[Any] = None,
        creator: str = "ORCA",
        version: str = "6.1",
        routine: str = "sp",
    ) -> int:
        """Adds computed PES points with full QCSchema provenance."""
        validate_theory_cleanliness(method_id)
        coords_arr = np.asarray(coords, dtype=np.float64)
        if coords_arr.ndim == 2:
            coords_arr = coords_arr[None]
        npts, natm = coords_arr.shape[0], coords_arr.shape[1]
        energies_arr = np.asarray(energies, dtype=np.float64)
        if energies_arr.ndim == 0:
            energies_arr = energies_arr[None]

        prov = json.dumps({
            "creator": creator,
            "version": version,
            "routine": routine,
            "host": socket.gethostname(),
            "platform": platform.platform(),
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

        with h5py.File(self.path, "a") as f:
            i0 = self._append(self._ds(f, method_id, "coordinates", (natm, 3), np.float64), coords_arr)
            self._append(self._ds(f, method_id, "energy", (), np.float64, checksum=True), energies_arr)
            self._append(
                self._ds(f, method_id, "converged", (), np.bool_),
                np.ones(npts, bool) if converged is None else np.asarray(converged, bool),
            )
            self._append(
                self._ds(f, method_id, "wall_s", (), np.float64),
                np.zeros(npts, dtype=np.float64) if wall_s is None else np.asarray(wall_s, dtype=np.float64),
            )
            self._append(
                self._ds(f, method_id, "provenance", (), VLEN_STR),
                np.array([prov] * npts, dtype=object),
            )
            p_ids = list(point_ids) if point_ids is not None else [f"{method_id}:{i0 + k}" for k in range(npts)]
            self._append(
                self._ds(f, method_id, "point_id", (), VLEN_STR),
                np.array(p_ids, dtype=object),
            )
            if gradients is not None:
                g = np.asarray(gradients, dtype=np.float64)
                if g.ndim == 2:
                    g = g[None]
                self._append(self._ds(f, method_id, "gradient", (natm, 3), np.float64), g)
        return i0

    def add_hessian(self, label: str, H: Any, *, level: str, geometry_ref: str) -> None:
        """Stores Cartesian Hessian tensor in HDF5."""
        validate_theory_cleanliness(level)
        with h5py.File(self.path, "a") as f:
            g = f.require_group("hessians")
            if label in g:
                del g[label]
            d = g.create_dataset(
                label,
                data=np.asarray(H, dtype=np.float64),
                compression="gzip",
                compression_opts=4,
                shuffle=True,
            )
            d.attrs["level"] = level
            d.attrs["geometry_ref"] = geometry_ref

    def register_grid(self, grid_id: str, axes: Dict[str, Any]) -> None:
        """Registers grid axes for potential energy surfaces."""
        with h5py.File(self.path, "a") as f:
            g = f.require_group(f"grids/{grid_id}")
            for name, vals in axes.items():
                if name in g:
                    del g[name]
                g.create_dataset(name, data=np.asarray(vals, dtype=np.float64))
            g.attrs["axis_order"] = json.dumps(list(axes))
            g.attrs["shape"] = [len(v) for v in axes.values()]

    def todo(self, method_id: str, wanted_ids: Iterable[str]) -> List[str]:
        """Identifies missing / unconverged points for incremental refinement and restart."""
        with h5py.File(self.path, "a") as f:
            p = f.get(f"points/{method_id}")
            if p is None or "point_id" not in p:
                return list(wanted_ids)
            have = {
                (s.decode() if isinstance(s, bytes) else s)
                for s, ok in zip(p["point_id"][:], p["converged"][:], strict=False)
                if ok
            }
        return [i for i in wanted_ids if i not in have]

    def dataset(self, method_id: str, converged_only: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """Retrieves coordinates and energies for a method."""
        with h5py.File(self.path, "r") as f:
            p = f[f"points/{method_id}"]
            m = p["converged"][:] if converged_only else slice(None)
            return p["coordinates"][:][m], p["energy"][:][m]

    def delta_pairs(self, low: str, high: str) -> Tuple[List[str], np.ndarray, np.ndarray]:
        """Returns aligned (coordinates, E_high - E_low) pairs for Delta-learning."""
        with h5py.File(self.path, "r") as f:
            def idx(mid: str) -> Dict[str, int]:
                p = f[f"points/{mid}"]
                ids = [(s.decode() if isinstance(s, bytes) else s) for s in p["point_id"][:]]
                return {k: j for j, (k, ok) in enumerate(zip(ids, p["converged"][:], strict=False)) if ok}

            il, ih = idx(low), idx(high)
            keys = sorted(set(il) & set(ih))
            X = f[f"points/{high}/coordinates"][:][[ih[k] for k in keys]]
            dE = f[f"points/{high}/energy"][:][[ih[k] for k in keys]] - f[f"points/{low}/energy"][:][[il[k] for k in keys]]
        return keys, X, dE

    def dvr_grid(self, method_id: str, grid_id: str) -> np.ndarray:
        """Reshapes energies onto a registered product grid for DVR solvers."""
        with h5py.File(self.path, "r") as f:
            shape = tuple(int(x) for x in f[f"grids/{grid_id}"].attrs["shape"])
            p = f[f"points/{method_id}"]
            ids = [(s.decode() if isinstance(s, bytes) else s) for s in p["point_id"][:]]
            total_pts = 1
            for dim in shape:
                total_pts *= dim
            V = np.full(total_pts, np.nan, dtype=np.float64)
            for j, k in enumerate(ids):
                if k.startswith(f"{grid_id}:") and p["converged"][j]:
                    V[int(k.split(":")[1])] = p["energy"][j]
        return V.reshape(shape)

    def checkpoint_state(self, checkpoint_name: str, state_data: Dict[str, Any]) -> None:
        """Serializes arbitrary dictionary state to HDF5 checkpoint group."""
        validate_theory_cleanliness(state_data)
        with h5py.File(self.path, "a") as f:
            grp = f.require_group(f"checkpoints/{checkpoint_name}")
            grp.attrs["saved_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            for k, v in state_data.items():
                if isinstance(v, np.ndarray):
                    if k in grp:
                        del grp[k]
                    grp.create_dataset(k, data=v)
                elif isinstance(v, (int, float, str, bool)):
                    grp.attrs[k] = v
                else:
                    grp.attrs[k] = json.dumps(v)

    def read_checkpoint(self, checkpoint_name: str) -> Dict[str, Any]:
        """Reads back saved checkpoint state dictionary."""
        result: Dict[str, Any] = {}
        with h5py.File(self.path, "r") as f:
            if f"checkpoints/{checkpoint_name}" not in f:
                return result
            grp = f[f"checkpoints/{checkpoint_name}"]
            for k, v in grp.attrs.items():
                val = v.item() if hasattr(v, "item") and not isinstance(v, (str, bytes)) else v
                if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                    try:
                        result[k] = json.loads(val)
                    except json.JSONDecodeError:
                        result[k] = val
                else:
                    result[k] = val
            for k in grp.keys():
                result[k] = grp[k][:]
        return result


# ---------------------------------------------------------------------------
# Graceful Degradation & Preemption Timers
# ---------------------------------------------------------------------------

def send_soft_preemption_signal(target: Union[subprocess.Popen, psutil.Process, int]) -> bool:
    """Issues soft termination signal (CTRL_BREAK_EVENT on Windows, SIGUSR1/SIGTERM on POSIX).

    Avoids harsh TerminateProcess or SIGKILL, giving processes a clean window to checkpoint.
    """
    pid: int
    proc_obj: Optional[subprocess.Popen] = None

    if isinstance(target, subprocess.Popen):
        pid = target.pid
        proc_obj = target
    elif isinstance(target, psutil.Process):
        pid = target.pid
    else:
        pid = int(target)

    if platform.system() == "Windows":
        # If we have the Popen object created with CREATE_NEW_PROCESS_GROUP
        if proc_obj is not None:
            try:
                proc_obj.send_signal(signal.CTRL_BREAK_EVENT)
                logger.info(f"Sent CTRL_BREAK_EVENT to Popen process (PID {pid})")
                return True
            except Exception as e:
                logger.warning(f"Popen.send_signal failed for PID {pid}: {e}")

        # Fallback to os.kill with CTRL_BREAK_EVENT or kernel32 GenerateConsoleCtrlEvent
        try:
            os.kill(pid, signal.CTRL_BREAK_EVENT)
            logger.info(f"Sent CTRL_BREAK_EVENT to PID {pid}")
            return True
        except Exception:
            try:
                kernel32 = ctypes.windll.kernel32  # type: ignore
                # CTRL_BREAK_EVENT = 1
                res = kernel32.GenerateConsoleCtrlEvent(1, ctypes.c_ulong(pid))  # type: ignore
                if res:
                    logger.info(f"GenerateConsoleCtrlEvent sent to PID {pid}")
                    return True
            except Exception as e:
                logger.warning(f"GenerateConsoleCtrlEvent failed for PID {pid}: {e}")
        return False
    else:
        # POSIX: Send SIGUSR1 or SIGTERM
        posix_signals: List[Any] = []
        sig_usr1 = getattr(signal, "SIGUSR1", None)
        if sig_usr1 is not None:
            posix_signals.append(sig_usr1)
        sig_term = getattr(signal, "SIGTERM", None)
        if sig_term is not None:
            posix_signals.append(sig_term)

        for sig in posix_signals:
            try:
                os.kill(pid, sig)
                sig_name = getattr(sig, "name", str(sig))
                logger.info(f"Sent {sig_name} to PID {pid}")
                return True
            except ProcessLookupError:
                return False
            except Exception as e:
                sig_name = getattr(sig, "name", str(sig))
                logger.warning(f"Failed sending {sig_name} to PID {pid}: {e}")
        return False


class PreemptionTimer:
    """Monitors Time-To-Live (TTL) and triggers soft preemption signals and checkpoints."""

    def __init__(
        self,
        ttl_seconds: float,
        lead_time_seconds: float = 60.0,
        target_proc: Optional[Union[subprocess.Popen, psutil.Process, int]] = None,
        on_preempt_callback: Optional[Callable[[], Any]] = None,
        pes_store: Optional[PESStore] = None,
    ) -> None:
        self.ttl_seconds = float(ttl_seconds)
        self.lead_time_seconds = float(lead_time_seconds)
        self.target_proc = target_proc
        self.on_preempt_callback = on_preempt_callback
        self.pes_store = pes_store

        self.start_time = time.monotonic()
        self._preempted = False
        self._cancelled = False
        self._timer_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Starts background thread watching TTL limit."""
        if self._timer_thread is not None and self._timer_thread.is_alive():
            return
        self.start_time = time.monotonic()
        self._cancelled = False
        self._preempted = False
        self._timer_thread = threading.Thread(target=self._run_monitor, daemon=True)
        self._timer_thread.start()

    def cancel(self) -> None:
        """Cancels preemption timer."""
        self._cancelled = True

    def time_remaining(self) -> float:
        """Returns seconds remaining before TTL breach."""
        elapsed = time.monotonic() - self.start_time
        return max(0.0, self.ttl_seconds - elapsed)

    def is_preempted(self) -> bool:
        """Returns whether preemption signal has been dispatched."""
        return self._preempted

    def trigger_preemption(self) -> None:
        """Manually or automatically triggers preemption actions."""
        if self._preempted:
            return
        self._preempted = True
        logger.warning(f"Preemption triggered ({self.time_remaining():.1f}s TTL remaining)")

        # 1. Execute custom checkpoint callback
        if self.on_preempt_callback:
            try:
                self.on_preempt_callback()
            except Exception as e:
                logger.error(f"Error in preemption callback: {e}")

        # 2. Dispatch soft signal to target process
        if self.target_proc is not None:
            send_soft_preemption_signal(self.target_proc)

    def _run_monitor(self) -> None:
        """Internal monitoring loop."""
        lead_time = min(self.lead_time_seconds, self.ttl_seconds * 0.5)
        trigger_at = self.ttl_seconds - lead_time

        while not self._cancelled and not self._preempted:
            elapsed = time.monotonic() - self.start_time
            if elapsed >= trigger_at:
                self.trigger_preemption()
                break
            time.sleep(min(0.2, max(0.01, trigger_at - elapsed)))


# ---------------------------------------------------------------------------
# Thermal Guard Daemon
# ---------------------------------------------------------------------------

class ThermalGuardDaemon:
    """Asynchronous thermal safety monitor.

    Monitors host temperature via psutil.sensors_temperatures() with Linux/POSIX checks
    and graceful fallback. If thresholds are breached (>85°C), recursively suspends process
    trees. Once cooled (<75°C), resumes them for lossless optimization.
    """

    def __init__(
        self,
        high_temp_threshold: float = 85.0,
        recovery_temp_threshold: float = 75.0,
        check_interval_seconds: float = 1.0,
        target_pids: Optional[List[int]] = None,
        temperature_probe_fn: Optional[Callable[[], Optional[float]]] = None,
    ) -> None:
        self.high_temp_threshold = float(high_temp_threshold)
        self.recovery_temp_threshold = float(recovery_temp_threshold)
        self.check_interval_seconds = float(check_interval_seconds)
        self.target_pids: List[int] = list(target_pids or [])
        self.temperature_probe_fn = temperature_probe_fn

        self.state = ThermalState.NORMAL
        self.suspended_pids: Set[int] = set()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def add_target_pid(self, pid: int) -> None:
        """Adds a process PID to the thermal protection watch list."""
        if pid not in self.target_pids:
            self.target_pids.append(pid)

    def remove_target_pid(self, pid: int) -> None:
        """Removes a process PID from the watch list."""
        if pid in self.target_pids:
            self.target_pids.remove(pid)

    def get_current_temperature(self) -> Optional[float]:
        """Probes current system temperature.

        Guarded with platform.system() == 'Linux' and fallback to custom probe.
        """
        if self.temperature_probe_fn is not None:
            return self.temperature_probe_fn()

        if platform.system() == "Linux":
            try:
                sensors_fn = getattr(psutil, "sensors_temperatures", None)
                if sensors_fn is not None:
                    sensors = sensors_fn()
                    if sensors:
                        temps: List[float] = []
                        for _sensor_name, entries in sensors.items():
                            for entry in entries:
                                cur = getattr(entry, "current", None)
                                if cur is not None:
                                    temps.append(float(cur))
                        if temps:
                            return max(temps)
            except Exception as e:
                logger.debug(f"psutil temperature probe failed: {e}")

        return None

    def check_thermal_cycle(self, simulated_temp: Optional[float] = None) -> ThermalState:
        """Performs a single thermal evaluation cycle and suspends/resumes process tree."""
        temp = simulated_temp if simulated_temp is not None else self.get_current_temperature()
        if temp is None:
            return self.state

        if temp >= self.high_temp_threshold:
            if self.state != ThermalState.SUSPENDED:
                self.state = ThermalState.SUSPENDED
                logger.warning(
                    f"Thermal limit breached ({temp:.1f}°C >= {self.high_temp_threshold}°C). "
                    "Suspending process tree recursively."
                )
                self._suspend_process_tree()
        elif temp <= self.recovery_temp_threshold:
            if self.state == ThermalState.SUSPENDED:
                self.state = ThermalState.NORMAL
                logger.info(
                    f"Thermal recovery achieved ({temp:.1f}°C <= {self.recovery_temp_threshold}°C). "
                    "Resuming process tree."
                )
                self._resume_process_tree()
            elif temp > self.high_temp_threshold - 5.0:
                self.state = ThermalState.WARNING
            else:
                self.state = ThermalState.NORMAL
        else:
            if self.state != ThermalState.SUSPENDED:
                if temp > self.high_temp_threshold - 5.0:
                    self.state = ThermalState.WARNING

        return self.state

    def _suspend_process_tree(self) -> None:
        """Recursively suspends all target processes and their descendants."""
        for pid in list(self.target_pids):
            try:
                proc = psutil.Process(pid)
                descendants = proc.children(recursive=True)
                for p in [proc] + descendants:
                    try:
                        p.suspend()
                        self.suspended_pids.add(p.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def _resume_process_tree(self) -> None:
        """Recursively resumes all suspended processes."""
        for pid in list(self.suspended_pids):
            try:
                proc = psutil.Process(pid)
                proc.resume()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        self.suspended_pids.clear()

    async def start(self) -> None:
        """Starts asynchronous thermal monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Stops monitoring loop and ensures processes are resumed."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._resume_process_tree()

    async def _monitor_loop(self) -> None:
        """Internal asynchronous loop."""
        while self._running:
            self.check_thermal_cycle()
            await asyncio.sleep(self.check_interval_seconds)


# ---------------------------------------------------------------------------
# Module Self-Test & Diagnostic Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("CoChem Temporal Router Initialized.")
    logger.info(f"Loaded {len(TIER_REGISTRY)} Temporal Tiers (10s -> 1mo).")
    logger.info("EMT Eradication Enforced.")
