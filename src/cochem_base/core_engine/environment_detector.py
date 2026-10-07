"""OS-native Stage 0 ingress; no container runtime is needed to inspect a host."""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform

from .preflight import PreflightValidationError


@dataclass(frozen=True)
class EnvironmentProfile:
    os_target: str
    system: str
    machine: str
    is_wsl: bool


def detect_environment() -> EnvironmentProfile:
    """Identify the four supported deployment tiers from the actual runtime."""
    system = platform.system()
    is_wsl = system == "Linux" and "microsoft" in platform.release().lower()
    if os.environ.get("CODESPACES", "").lower() == "true":
        target = "Codespaces"
    elif system == "Windows" or is_wsl:
        target = "Local-Windows"
    elif system == "Darwin":
        target = "Local-MacOS"
    elif system == "Linux":
        target = "Local-Linux"
    else:
        raise PreflightValidationError(f"Unsupported operating system: {system!r}")
    return EnvironmentProfile(target, system, platform.machine(), is_wsl)
