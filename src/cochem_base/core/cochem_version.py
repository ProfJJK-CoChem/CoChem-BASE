"""Authoritative OS-Agnostic Dynamic VCS Provenance & Container Introspection.

Provides robust environment discovery compliant with FAIR Principle R1.2 across:
- Git Repositories (local development)
- Build Manifests (.build_manifest.json)
- Installed Distribution Packages (importlib.metadata inside stripped Docker containers and HPC wheels)
- Untracked Air-Gapped Environments
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _find_git_root(start_path: Path) -> Optional[Path]:
    """Traverse directory parents to locate genuine .git directory or file."""
    curr = start_path.resolve()
    for p in [curr, *curr.parents]:
        git_target = p / ".git"
        if git_target.exists():
            return p
    return None


def get_vcs_provenance(root_path: Optional[Path] = None) -> Dict[str, Any]:
    """Dynamically determine software version and source provenance hierarchy [D].

    Hierarchy:
    1. Git Repository Check: Queries active commit SHA, branch, dirty status.
    2. Build Manifest Check: Checks for .build_manifest.json in package or COCHEM_ROOT.
    3. Distribution Package Introspection (PEP 566 importlib.metadata).
    4. Safe Fallback (UNTRACKED_BUILD).

    Args:
        root_path: Optional override path to search for repository anchor.

    Returns:
        Dict[str, Any]: Structured VCS provenance metadata dictionary.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Determine starting path anchor
    start_dir: Optional[Path] = None
    if root_path is not None:
        start_dir = Path(root_path).resolve()
    else:
        # Dynamic module anchor
        start_dir = Path(__file__).resolve().parent

    # 1. Git Repository Discovery
    if start_dir is not None:
        git_dir = _find_git_root(start_dir)
        git_cmd = shutil.which("git")
        if git_dir is not None and git_cmd is not None:
            try:
                sha_proc = subprocess.run(
                    [git_cmd, "rev-parse", "HEAD"],
                    cwd=str(git_dir),
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if sha_proc.returncode == 0 and sha_proc.stdout.strip():
                    sha = sha_proc.stdout.strip()
                    branch_proc = subprocess.run(
                        [git_cmd, "rev-parse", "--abbrev-ref", "HEAD"],
                        cwd=str(git_dir),
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False,
                    )
                    branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "unknown"

                    dirty_proc = subprocess.run(
                        [git_cmd, "status", "--porcelain"],
                        cwd=str(git_dir),
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False,
                    )
                    is_dirty = bool(dirty_proc.stdout.strip()) if dirty_proc.returncode == 0 else False

                    return {
                        "vcs_type": "git",
                        "commit_sha": sha,
                        "branch": branch,
                        "is_dirty": is_dirty,
                        "status": "GIT_REPOSITORY",
                        "git_root": str(git_dir),
                        "discovered_utc": timestamp,
                    }
            except Exception:
                pass

    # 2. Build Manifest Discovery
    manifest_candidates = []
    if root_path is not None:
        manifest_candidates.append(Path(root_path) / ".build_manifest.json")
    if os.environ.get("COCHEM_ROOT"):
        manifest_candidates.append(Path(os.environ["COCHEM_ROOT"]) / ".build_manifest.json")
    manifest_candidates.append(Path(__file__).resolve().parents[2] / ".build_manifest.json")

    for mc in manifest_candidates:
        if mc.exists():
            try:
                import json

                data = json.loads(mc.read_text(encoding="utf-8"))
                return {
                    "vcs_type": "build_manifest",
                    "version": data.get("version", "unknown"),
                    "build_id": data.get("build_id", "unknown"),
                    "manifest_path": str(mc),
                    "status": "BUILD_MANIFEST",
                    "discovered_utc": timestamp,
                }
            except Exception:
                pass

    # 3. Distribution Package Introspection (importlib.metadata)
    pkg_names = ["CoChem-BASE", "cochem_base", "cochem-base"]
    for pkg in pkg_names:
        try:
            dist = importlib.metadata.distribution(pkg)
            dist_version = dist.version
            dist_files = dist.files
            installer = dist.read_text("INSTALLER") or "unknown"
            return {
                "vcs_type": "installed_wheel",
                "version": dist_version,
                "installer": installer.strip(),
                "file_count": len(dist_files) if dist_files else 0,
                "package_name": pkg,
                "status": "DISTRIBUTION_PACKAGE",
                "discovered_utc": timestamp,
            }
        except importlib.metadata.PackageNotFoundError:
            continue

    # 4. Clean Fallback for Untracked Environments
    return {
        "vcs_type": "untracked",
        "version": "0.1.0-untracked",
        "status": "UNTRACKED_BUILD",
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "discovered_utc": timestamp,
    }


__all__ = [
    "get_vcs_provenance",
]
