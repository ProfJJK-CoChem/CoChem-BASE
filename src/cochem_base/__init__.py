"""CoChem-BASE: Scientific Computational Chemistry & Spectroscopy Ecosystem.

Canonical top-level package for CoChem-BASE (replacing legacy PEP-420 namespace
packaging so CoChem-BASE is the single distribution owner of ``cochem_base``).
Provides runtime platform introspection, versioning parity, and lazy submodule
re-exports without forcing optional desktop GUI or heavy accelerator imports.
"""
from __future__ import annotations

import importlib
import os
import platform
import sys
from types import ModuleType
from typing import Any, Dict

from cochem_base._version import __version__, get_version

__author__ = "CoChem Team"
__license__ = "Apache-2.0"

_LAZY_SUBMODULES: tuple[str, ...] = (
    "analysis",
    "bench_engine",
    "calc",
    "chain",
    "chemistry",
    "cli",
    "cochem_core",
    "concurrency",
    "config",
    "config_loader",
    "core",
    "core_engine",
    "data",
    "diagnostics",
    "engines",
    "environment",
    "exceptions",
    "export_utils",
    "formatters",
    "geometry",
    "harvesters",
    "intake",
    "interfaces",
    "managers",
    "ml",
    "mm",
    "orchestrator",
    "path_sanitization",
    "physics",
    "process_cleanup",
    "provenance",
    "result_evidence",
    "schemas",
    "spectroscopy",
    "theory_matrix",
    "topology",
    "validators",
)


def check_runtime_environment() -> Dict[str, Any]:
    """Introspect host runtime platform, Python version, and execution tier.

    Verifies Python >= 3.10 and classifies the host execution tier
    (LOCAL_WORKSTATION, WSL2_WORKSTATION, HPC_CLUSTER, CI_PIPELINE, CODESPACES).
    """
    if sys.version_info < (3, 10):
        raise RuntimeError(
            f"CoChem-BASE requires Python 3.10 or higher. Found {sys.version}"
        )

    system_name = platform.system()
    release_str = platform.release()
    tier = "LOCAL_WORKSTATION"

    if os.environ.get("CODESPACES") == "true" or os.environ.get(
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN"
    ):
        tier = "CODESPACES"
    elif (
        "SLURM_JOB_ID" in os.environ
        or "PBS_JOBID" in os.environ
        or "LSB_JOBID" in os.environ
    ):
        tier = "HPC_CLUSTER"
    elif os.environ.get("CI") == "true":
        tier = "CI_PIPELINE"
    elif "microsoft" in release_str.lower() or "WSL_DISTRO_NAME" in os.environ:
        tier = "WSL2_WORKSTATION"

    return {
        "version": __version__,
        "python_version": platform.python_version(),
        "platform": system_name,
        "platform_release": release_str,
        "architecture": platform.machine(),
        "tier": tier,
        "is_64bit": sys.maxsize > 2**32,
    }


def __getattr__(name: str) -> ModuleType:
    if name in _LAZY_SUBMODULES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "get_version",
    "check_runtime_environment",
    *_LAZY_SUBMODULES,
]
