"""Ephemeral Sandbox Context & Path Jailbreak Defense.

Strictly adheres to:
- CoChem Anti-Spoofing Protocol v2
- Tripartite Storage Air-Gap Architecture (Tier 3 $COCH_SCRATCH isolation)
- Suggestion #68: atexit callback unregistration on context exit eliminating memory leaks.
"""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional, Union

from cochem_base.core.exceptions import AirGapBoundaryError

logger = logging.getLogger("cochem_sandbox")


class SandboxContext:
    """Manages ephemeral calculation workspaces adhering to Tripartite Air-Gap Domain C."""

    def __init__(
        self,
        scratch_root: Optional[Union[Path, str, Any]] = None,
        prefix: str = "cochem_job_",
    ) -> None:
        # Support SandboxConfig object if passed as first argument
        resolved_root: Optional[Path] = None
        if scratch_root is not None:
            if hasattr(scratch_root, "scratch_parent_dir") and scratch_root.scratch_parent_dir is not None:
                resolved_root = Path(scratch_root.scratch_parent_dir)
            elif isinstance(scratch_root, (str, Path)):
                resolved_root = Path(scratch_root)
        self.scratch_root: Path = self._resolve_and_validate_scratch_root(resolved_root)
        self.prefix: str = prefix
        self.path: Optional[Path] = None
        self._cleaned: bool = False

    def _resolve_and_validate_scratch_root(self, root: Optional[Path]) -> Path:
        if root is None:
            root = Path(os.environ.get("COCH_SCRATCH", os.environ.get("COCHEM_SCRATCH_DIR", "/tmp/cochem_scratch")))
        resolved = root.resolve()

        # Enforce Tripartite Air-Gap: Prohibit sandbox creation in Tier 1 ($COCH_SRC) or Tier 2 ($COCH_DATA)
        src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
        data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()
        if src_dir.exists() and (src_dir == resolved or src_dir in resolved.parents):
            raise AirGapBoundaryError(
                f"Cannot create ephemeral sandbox inside Tier 1 ($COCH_SRC): {resolved}",
                details={"attempted_path": str(resolved), "tier": "Tier 1"},
            )
        if data_dir.exists() and (data_dir == resolved or data_dir in resolved.parents):
            raise AirGapBoundaryError(
                f"Cannot create ephemeral sandbox inside Tier 2 ($COCH_DATA): {resolved}",
                details={"attempted_path": str(resolved), "tier": "Tier 2"},
            )
        return resolved

    @property
    def root(self) -> Optional[Path]:
        """Backward-compatible alias for self.path."""
        return self.path

    def __enter__(self) -> SandboxContext:
        self.scratch_root.mkdir(parents=True, exist_ok=True)
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix, dir=self.scratch_root))
        self._cleaned = False
        atexit.register(self.cleanup)
        return self

    def cleanup(self) -> None:
        """Idempotently cleans up scratch directory and removes atexit registration."""
        if self._cleaned:
            return
        self._cleaned = True
        try:
            atexit.unregister(self.cleanup)
        except Exception as exc:
            logger.debug("atexit unregister error: %s", exc)
        if self.path is not None and self.path.exists():
            try:
                shutil.rmtree(self.path, ignore_errors=True)
            except Exception as exc:
                logger.debug("shutil.rmtree error during cleanup: %s", exc)

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.cleanup()


__all__ = [
    "SandboxContext",
]
