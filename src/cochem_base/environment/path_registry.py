"""CoChem Ecosystem Dynamic Path Registry.

Compliant with Tripartite Filesystem Air-Gap (Ring 1 Static, Ring 2 Scratch, Ring 3 Artifacts).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class PathRegistry:
    """Authoritative filesystem registry for CoChem artifacts and scratch paths.

    Enforces the Tripartite Filesystem Air-Gap:
    - Ring 1 (T_repo): Static immutable repository root
    - Ring 2 (T_scratch): Ephemeral isolated scratch workspaces
    - Ring 3 (T_store): Persistent curated HDF5 datastores and artifacts
    """

    @classmethod
    def get_artifacts_dir(cls) -> Path:
        """Resolve persistent artifacts directory backed by COCHEM_ARTIFACTS_DIR.

        Returns
        -------
        Path
            Resolved directory path guaranteed to exist on disk.
        """
        env_path = os.environ.get("COCHEM_ARTIFACTS_DIR") or os.environ.get("COCHEM_ARTIFACTS")
        if env_path:
            p = Path(env_path).resolve()
        else:
            p = Path(tempfile.gettempdir()) / "cochem" / "artifacts"

        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def create_scratch_dir(cls, prefix: str = "scratch") -> Path:
        """Create a dynamic, isolated ephemeral scratch subdirectory for worker execution.

        Parameters
        ----------
        prefix : str
            Prefix identifier for the temporary directory.

        Returns
        -------
        Path
            Unique, newly created scratch directory.
        """
        env_scratch = (
            os.environ.get("COCHEM_SCRATCH_DIR")
            or os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TMPDIR")
        )
        if env_scratch:
            base_dir = Path(env_scratch).resolve()
        else:
            base_dir = Path(tempfile.gettempdir()) / "cochem" / "scratch"

        base_dir.mkdir(parents=True, exist_ok=True)
        scratch_path = Path(tempfile.mkdtemp(prefix=f"{prefix}_", dir=str(base_dir))).resolve()
        return scratch_path


__all__ = ["PathRegistry"]
