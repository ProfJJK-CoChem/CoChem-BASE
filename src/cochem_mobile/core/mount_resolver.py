"""Host-to-Container Mount and Path Resolver for CoChem-Mobile (REQ-MOB-005).

Provides bidirectional path and mount translation across 6-Tier environments:
GitHub Codespaces, Local-Windows WSL, Local-macOS OrbStack, Local-Linux Debian,
GitHub Actions, and HPC clusters.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import List, Optional, Sequence, Union



class EnvironmentType(str, Enum):
    """Supported 6-Tier execution environments."""
    WINDOWS = "windows"
    WSL = "wsl"
    MACOS_ORBSTACK = "macos_orbstack"
    LINUX_DEBIAN = "linux_debian"
    GITHUB_CODESPACES = "github_codespaces"
    GITHUB_ACTIONS = "github_actions"
    HPC = "hpc"


class SecurityPathTraversalError(Exception):
    """Raised when an illegal path traversal or jail breakout is detected."""


@dataclass(frozen=True)
class MountMapping:
    """Mount mapping between host path and container path."""
    host_path: Path
    container_path: PurePosixPath
    read_only: bool = False


class HostToContainerMountResolver:
    """Bidirectional path translator between host systems and container sandboxes.

    Strictly uses pathlib.Path, eliminates hardcoded user paths/drive letters,
    and enforces path traversal defense.
    """

    def __init__(
        self,
        default_target_env: EnvironmentType = EnvironmentType.LINUX_DEBIAN,
        default_host_env: Optional[EnvironmentType] = None,
        jail_roots: Optional[Sequence[Union[str, Path]]] = None,
    ) -> None:
        self.target_env = default_target_env
        self.host_env = default_host_env or self.detect_host_environment()
        self.mount_registry: List[MountMapping] = []
        self.jail_roots: List[Path] = []
        if jail_roots:
            for root in jail_roots:
                self.register_jail_root(root)

    @staticmethod
    def detect_host_environment() -> EnvironmentType:
        """Detect current execution environment automatically."""
        if os.environ.get("CODESPACES") == "true":
            return EnvironmentType.GITHUB_CODESPACES
        if os.environ.get("GITHUB_ACTIONS") == "true":
            return EnvironmentType.GITHUB_ACTIONS
        if "SLURM_JOB_ID" in os.environ or "PBS_JOBID" in os.environ or "LSB_JOBID" in os.environ:
            return EnvironmentType.HPC
        if "WSL_DISTRO_NAME" in os.environ or "WSL_INTEROP" in os.environ:
            return EnvironmentType.WSL

        platform_system = sys.platform.lower()
        if platform_system.startswith("win"):
            return EnvironmentType.WINDOWS
        elif platform_system.startswith("darwin"):
            return EnvironmentType.MACOS_ORBSTACK
        else:
            # Check for WSL inside Linux proc version
            try:
                proc_ver = Path("/proc/version")
                if proc_ver.exists():
                    text = proc_ver.read_text(encoding="utf-8").lower()
                    if "microsoft" in text or "wsl" in text:
                        return EnvironmentType.WSL
            except OSError:
                pass
            return EnvironmentType.LINUX_DEBIAN

    def register_jail_root(self, root_path: Union[str, Path]) -> Path:
        """Register a valid jail root to restrict path operations."""
        resolved = Path(root_path).resolve()
        if resolved not in self.jail_roots:
            self.jail_roots.append(resolved)
        return resolved

    def register_mount(
        self,
        host_path: Union[str, Path],
        container_path: Union[str, PurePosixPath],
        read_only: bool = False,
    ) -> MountMapping:
        """Register an explicit host-to-container mount directory pair."""
        norm_host = Path(host_path).resolve()
        norm_container = PurePosixPath(str(container_path).replace("\\", "/"))
        mapping = MountMapping(
            host_path=norm_host,
            container_path=norm_container,
            read_only=read_only,
        )
        # Avoid duplicate mounts
        self.mount_registry = [m for m in self.mount_registry if m.host_path != norm_host]
        self.mount_registry.append(mapping)
        # Sort by length descending for longest-prefix match
        self.mount_registry.sort(key=lambda m: len(str(m.host_path)), reverse=True)
        return mapping

    def validate_path_security(
        self,
        path: Union[str, Path],
        jail_roots: Optional[Sequence[Union[str, Path]]] = None,
    ) -> Path:
        """Enforce path security: check for null bytes, directory traversal, and jail confinement."""
        path_str = str(path)
        if "\0" in path_str:
            raise SecurityPathTraversalError("Null byte detected in path string.")

        resolved = Path(path).resolve()

        active_jails = [Path(j).resolve() for j in jail_roots] if jail_roots else self.jail_roots
        if active_jails:
            is_contained = False
            for jail in active_jails:
                try:
                    resolved.relative_to(jail)
                    is_contained = True
                    break
                except ValueError:
                    continue
            if not is_contained:
                raise SecurityPathTraversalError(
                    f"Path '{resolved}' breaches active jail roots: {[str(j) for j in active_jails]}"
                )

        return resolved

    def host_to_container(
        self,
        host_path: Union[str, Path],
        target_env: Optional[EnvironmentType] = None,
        custom_mappings: Optional[Sequence[MountMapping]] = None,
    ) -> PurePosixPath:
        """Translate a host filesystem path into a container-compatible POSIX path."""
        target = target_env or self.target_env
        mappings = list(custom_mappings) if custom_mappings else self.mount_registry

        # Normalize host path
        resolved_host = Path(host_path).resolve()
        resolved_str = str(resolved_host)

        # Check explicit mount registrations with longest-prefix match
        for mapping in mappings:
            try:
                rel = resolved_host.relative_to(mapping.host_path)
                rel_posix = PurePosixPath(rel.as_posix())
                return mapping.container_path / rel_posix
            except ValueError:
                continue

        # Handle implicit Windows to WSL / Linux translation
        drive_match = re.match(r"^([a-zA-Z]):[\\/](.*)", resolved_str)
        if drive_match:
            drive_letter = drive_match.group(1).lower()
            rest = drive_match.group(2).replace("\\", "/")
            if target == EnvironmentType.WSL:
                return PurePosixPath(f"/mnt/{drive_letter}/{rest}")
            elif target in (
                EnvironmentType.LINUX_DEBIAN,
                EnvironmentType.GITHUB_CODESPACES,
                EnvironmentType.HPC,
                EnvironmentType.GITHUB_ACTIONS,
            ):
                return PurePosixPath(f"/workspace/{drive_letter}/{rest}")
            elif target == EnvironmentType.MACOS_ORBSTACK:
                return PurePosixPath(f"/Volumes/{drive_letter}/{rest}")

        # Linux/macOS POSIX path to container POSIX path
        posix_str = resolved_host.as_posix()
        return PurePosixPath(posix_str)

    def container_to_host(
        self,
        container_path: Union[str, PurePosixPath, Path],
        host_env: Optional[EnvironmentType] = None,
        custom_mappings: Optional[Sequence[MountMapping]] = None,
    ) -> Path:
        """Translate a container-side POSIX path back into host filesystem path."""
        host = host_env or self.host_env
        mappings = list(custom_mappings) if custom_mappings else self.mount_registry

        norm_container = PurePosixPath(str(container_path).replace("\\", "/"))
        container_str = str(norm_container)

        # Check explicit mount registrations
        for mapping in mappings:
            try:
                rel = norm_container.relative_to(mapping.container_path)
                return mapping.host_path / Path(rel.as_posix())
            except ValueError:
                continue

        # Handle WSL /mnt/<drive>/... to Windows host
        wsl_match = re.match(r"^/mnt/([a-zA-Z])/(.*)", container_str)
        if wsl_match and host == EnvironmentType.WINDOWS:
            drive_letter = wsl_match.group(1).upper()
            rest = wsl_match.group(2).replace("/", os.sep)
            return Path(f"{drive_letter}:{os.sep}{rest}")

        # Handle /workspace/<drive>/... to Windows host
        workspace_match = re.match(r"^/workspace/([a-zA-Z])/(.*)", container_str)
        if workspace_match and host == EnvironmentType.WINDOWS:
            drive_letter = workspace_match.group(1).upper()
            rest = workspace_match.group(2).replace("/", os.sep)
            return Path(f"{drive_letter}:{os.sep}{rest}")

        return Path(container_str)

    @staticmethod
    def audit_banned_patterns(command_or_path: str) -> List[str]:
        """Scan a path or command for banned hardcoded patterns ($HOME, ~, raw user paths)."""
        violations: List[str] = []
        if "$HOME" in command_or_path:
            violations.append("$HOME token found; must use resolved Path objects")
        if re.search(r"(^|[\s\"'])~[/\\a-zA-Z0-9_.-]*", command_or_path):
            violations.append("Tilde expansion pattern '~' found; must use explicit Path")
        if re.search(r"/home/[a-zA-Z0-9_-]+", command_or_path):
            violations.append("Hardcoded /home/<user> directory pattern found")
        if re.search(r"C:\\Users\\[a-zA-Z0-9_-]+", command_or_path, re.IGNORECASE):
            violations.append("Hardcoded C:\\Users\\<user> directory pattern found")
        return violations
