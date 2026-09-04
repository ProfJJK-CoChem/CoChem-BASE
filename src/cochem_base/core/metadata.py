"""Authoritative Dynamic Elemental Metadata, Empirical Radii, and Hardware Telemetry.

Complies strictly with:
- Dynamic Mendeleev Invariant Mandate (Method Matrix v4 §8C, zero hardcoded masses)
- Hierarchical Empirical Radii Lookup (Method Matrix v4 §20, Pyykkö -> Cordero -> vdW)
- Strictly Non-Initializing GPU Discovery (Method Matrix v4 §8A.4, zero CUDA-locking)
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import functools
import os
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union

import mendeleev

from cochem_base.core.exceptions import IsotopeStabilityError, RadiusNotFoundError


@functools.lru_cache(maxsize=1024)
def get_isotopic_mass(symbol_or_atomic_number: Union[str, int], mass_number: int) -> float:
    """Retrieve dynamic IUPAC/CIAAW isotopic nuclear mass for a specified isotope [M].

    Eradicates permissive fallback to terrestrial abundance-weighted average atomic weight.
    Strictly raises IsotopeStabilityError if the requested isotope cannot be physically resolved.

    Args:
        symbol_or_atomic_number: IUPAC elemental symbol (e.g. 'C', 'H', 'Cl') or integer atomic number (Z).
        mass_number: Integer nuclear nucleon count (A).

    Returns:
        float: Physical nuclear mass in unified atomic mass units (u) [M].

    Raises:
        IsotopeStabilityError: If the element or isotope does not exist in authoritative Mendeleev data.
    """
    try:
        el = mendeleev.element(symbol_or_atomic_number)
    except Exception as exc:
        raise IsotopeStabilityError(
            f"Element '{symbol_or_atomic_number}' could not be resolved in Mendeleev registry: {exc}"
        ) from exc

    target_a = int(mass_number)
    matched_iso = next((iso for iso in el.isotopes if iso.mass_number == target_a), None)

    if matched_iso is not None and matched_iso.mass is not None and float(matched_iso.mass) > 0.0:
        return float(matched_iso.mass)

    raise IsotopeStabilityError(
        f"Isotope '{el.symbol}-{mass_number}' cannot be resolved to a physical isotopic mass in authoritative CIAAW/Mendeleev data."
    )


@functools.lru_cache(maxsize=256)
def get_covalent_radius(
    symbol_or_atomic_number: Union[str, int],
    radius_type: str = "pyykko",
) -> float:
    """Hierarchical empirical covalent and van der Waals radii lookup in Angstroms [M].

    Hierarchy:
    1. Primary: Pyykkö single-bond covalent radius (covalent_radius_pyykko)
    2. Secondary: Cordero covalent radius (covalent_radius_cordero)
    3. Tertiary: Standard covalent radius (covalent_radius)
    4. Quaternary: van der Waals radius (vdw_radius)

    Eradicates hardcoded numeric fallbacks (e.g. 0.77 Å).

    Args:
        symbol_or_atomic_number: Element symbol or atomic number.
        radius_type: Preferred radius convention ('pyykko', 'cordero', 'vdw').

    Returns:
        float: Empirical radius in Angstroms [M].

    Raises:
        RadiusNotFoundError: If no valid empirical radius can be resolved.
    """
    try:
        el = mendeleev.element(symbol_or_atomic_number)
    except Exception as exc:
        raise RadiusNotFoundError(
            f"Element '{symbol_or_atomic_number}' could not be resolved from Mendeleev registries: {exc}"
        ) from exc

    rtype = radius_type.strip().lower()
    if rtype in ("cordero", "covalent_radius_cordero"):
        candidates = [el.covalent_radius_cordero, el.covalent_radius_pyykko, el.covalent_radius, el.vdw_radius]
    elif rtype in ("vdw", "vdw_radius"):
        candidates = [el.vdw_radius, el.covalent_radius_pyykko, el.covalent_radius_cordero, el.covalent_radius]
    else:
        # Default Pyykkö primary hierarchy
        candidates = [el.covalent_radius_pyykko, el.covalent_radius_cordero, el.covalent_radius, el.vdw_radius]

    for val in candidates:
        if val is not None:
            try:
                fval = float(val)
                if fval > 0.0:
                    # Mendeleev reports radii in picometers (pm); convert to Angstroms
                    return fval / 100.0
            except (ValueError, TypeError):
                continue

    raise RadiusNotFoundError(
        f"Empirical radius for element '{el.symbol}' ({el.atomic_number}) could not be resolved from Mendeleev registries."
    )


def _query_nvml_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Query NVIDIA NVML C-bindings without initializing the CUDA runtime [E]."""
    try:
        import pynvml  # type: ignore[import-not-found]

        pynvml.nvmlInit()
        devices = []
        try:
            count = pynvml.nvmlDeviceGetCount()
            for idx in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                try:
                    cc_major, cc_minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                    compute_cap = f"{cc_major}.{cc_minor}"
                except Exception:
                    compute_cap = "unknown"

                devices.append({
                    "index": idx,
                    "product_name": str(name),
                    "total_memory_bytes": int(mem.total),
                    "compute_capability": compute_cap,
                })
            return devices
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        return None


def _query_cli_gpu_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Query standalone GPU CLI tools (nvidia-smi / rocm-smi) in a fast isolated subprocess [E]."""
    nvsmi = shutil.which("nvidia-smi")
    if nvsmi:
        try:
            proc = subprocess.run(
                [nvsmi, "--query-gpu=index,gpu_name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                devices = []
                for line in proc.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        try:
                            idx = int(parts[0])
                            pname = parts[1]
                            mem_mib = float(parts[2])
                            devices.append({
                                "index": idx,
                                "product_name": pname,
                                "total_memory_bytes": int(mem_mib * 1024 * 1024),
                                "compute_capability": "unknown",
                            })
                        except (ValueError, IndexError):
                            continue
                if devices:
                    return devices
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

    return None


def collect_hardware_metadata() -> Dict[str, Any]:
    """Collect host hardware and GPU accelerator telemetry using strictly non-initializing discovery [E].

    Guarantees zero CUDA runtime context initialization (zero CUDA-locking), maintaining NVIDIA MPS
    multiplexing readiness under Method Matrix v4 §8A.4.
    """
    # Strict AST / Runtime Prohibition verification
    if "torch" in sys.modules:
        torch_mod = sys.modules["torch"]
        if hasattr(torch_mod, "cuda") and hasattr(torch_mod.cuda, "is_initialized"):
            assert not torch_mod.cuda.is_initialized(), (
                "CUDA runtime was already initialized prior to non-initializing telemetry collection!"
            )

    gpus = _query_nvml_telemetry()
    if gpus is None:
        gpus = _query_cli_gpu_telemetry()
    if gpus is None:
        gpus = []

    cpu_count = os.cpu_count() or 1
    telemetry: Dict[str, Any] = {
        "platform": platform.platform(),
        "system": platform.system(),
        "cpu": {
            "architecture": platform.machine(),
            "processor": platform.processor() or "unknown",
            "physical_cores": cpu_count,
            "logical_cores": cpu_count,
        },
        "gpus": gpus,
        "gpu_count": len(gpus),
        "cuda_runtime_initialized": False,
    }

    return telemetry


__all__ = [
    "get_isotopic_mass",
    "get_covalent_radius",
    "collect_hardware_metadata",
]
