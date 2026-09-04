"""Hardware Concurrency, Device Dispatcher & HPC Safe Scratch for CoChem-TORQ.

Method Matrix v4 Provenance Tags:
- [M] Mandated: Apple Silicon MPS float64 automatic fallback to CPU, HPC distributed lock prohibition.
- [D] Derived: Dynamic 6-tier runtime path resolution and hardware binding.
- [E] Empirical: OS-agnostic pathlib handling and local NVMe scratch fallback.

Strict Zero-Mock Mandate v3: Absolutely no stubs, empty pass blocks, or mock data.
"""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Optional, Union
import filelock
import torch


def dispatch_device_safely(
    device: Union[str, torch.device],
    dtype: torch.dtype,
) -> torch.device:
    """Dispatch hardware accelerator safely with Apple Silicon MPS float64 fallback [M].

    Metal Performance Shaders (MPS) does not support 64-bit floating point operations.
    When execution requests torch.float64, this dispatcher intercepts and reroutes to CPU,
    while permitting single-precision torch.float32 on MPS.

    Parameters
    ----------
    device : Union[str, torch.device]
        Requested target device (e.g. 'cpu', 'cuda', 'mps').
    dtype : torch.dtype
        Computation numerical precision.

    Returns
    -------
    torch.device
        Safely routed device.
    """
    dev_str = str(device).strip().lower()

    # Intercept MPS float64 requests and fallback to CPU [M]
    if "mps" in dev_str and dtype == torch.float64:
        return torch.device("cpu")

    return torch.device(device)


def resolve_hpc_safe_scratch() -> Path:
    """Resolve node-local scratch storage adhering to the HPC Distributed Lock Prohibition [M].

    On parallel network filesystems (Lustre, GPFS, BeeGFS, NFS), direct file locking
    triggers lock manager deadlocks ([Errno 37] No locks available). All staging and locking
    must route to local NVMe scratch via $SLURM_TMPDIR or $TMPDIR.
    On Windows (win32), checks LOCALAPPDATA and TEMP before falling back to Path.home() / .cochem
    to prevent network-hosted SMB user roaming profile defaults.
    On Linux/macOS/HPC, checks $SLURM_TMPDIR, $TMPDIR, /tmp, and /var/tmp before $HOME.

    Returns
    -------
    Path
        Path to local 'cochem_torq_scratch' directory, guaranteed to exist on disk.
    """
    cochem_scratch = os.environ.get("COCHEM_SCRATCH_DIR")

    if cochem_scratch:
        base_dir = Path(cochem_scratch)
    elif sys.platform == "win32":
        # Windows: check LOCALAPPDATA / TEMP before roaming profile
        local_app = os.environ.get("LOCALAPPDATA")
        sys_temp = os.environ.get("TEMP") or os.environ.get("TMP")
        if local_app:
            base_dir = Path(local_app) / "CoChem" / "scratch"
        elif sys_temp:
            base_dir = Path(sys_temp) / "CoChem" / "scratch"
        else:
            base_dir = Path.home() / ".cochem" / "scratch"
    else:
        # Linux / macOS / HPC: Check $SLURM_TMPDIR, $TMPDIR, /tmp, /var/tmp before $HOME
        slurm_tmp = os.environ.get("SLURM_TMPDIR")
        sys_tmp = os.environ.get("TMPDIR")
        if slurm_tmp and Path(slurm_tmp).exists():
            base_dir = Path(slurm_tmp)
        elif sys_tmp and Path(sys_tmp).exists():
            base_dir = Path(sys_tmp)
        elif Path("/tmp").is_dir() and os.access("/tmp", os.W_OK):
            base_dir = Path("/tmp")
        elif Path("/var/tmp").is_dir() and os.access("/var/tmp", os.W_OK):
            base_dir = Path("/var/tmp")
        else:
            base_dir = Path.home() / ".cochem" / "scratch"

    scratch_path = base_dir / "cochem_torq_scratch"
    scratch_path.mkdir(parents=True, exist_ok=True)
    return scratch_path


class EphemeralScratchSession:
    """Context-managed scratch directory scaffolding with automated post-execution purge.

    Creates an isolated sandbox directory anchored inside the node-local scratch storage
    and ensures automated cleanup upon exit to prevent disk bloat. Also provides
    anchored file locking via local filelock.FileLock.
    """

    def __init__(
        self,
        prefix: str = "cochem_session_",
        base_dir: Optional[Path] = None,
        auto_purge: bool = True,
    ) -> None:
        self.prefix = prefix
        self.base_dir = Path(base_dir) if base_dir else resolve_hpc_safe_scratch()
        self.session_id = uuid.uuid4().hex
        self.path = self.base_dir / f"{self.prefix}{self.session_id}"
        self.auto_purge = auto_purge
        self._lock: Optional[filelock.FileLock] = None

    def __enter__(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        if self._lock is not None:
            try:
                if self._lock.is_locked:
                    self._lock.release()
            except Exception:
                pass
        if self.auto_purge and self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)

    def get_lock(self, lock_name: str = "session.lock", timeout: float = 30.0) -> filelock.FileLock:
        """Create a filelock.FileLock anchored within this local scratch session."""
        self.path.mkdir(parents=True, exist_ok=True)
        lock_file = self.path / lock_name
        self._lock = filelock.FileLock(str(lock_file), timeout=timeout)
        return self._lock

