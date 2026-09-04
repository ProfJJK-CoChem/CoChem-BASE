"""Hardware Concurrency, Device Dispatcher & HPC Safe Scratch for CoChem-TORQ.

Method Matrix v4 Provenance Tags:
- [M] Mandated: Apple Silicon MPS float64 automatic fallback to CPU, HPC distributed lock prohibition.
- [D] Derived: Dynamic 6-tier runtime path resolution and hardware binding.
- [E] Empirical: OS-agnostic pathlib handling and local NVMe scratch fallback.

Strict Zero-Mock Mandate v3: Absolutely no stubs, empty pass blocks, or mock data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union
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

    Returns
    -------
    Path
        Path to local 'cochem_torq_scratch' directory, guaranteed to exist on disk.
    """
    slurm_tmp = os.environ.get("SLURM_TMPDIR")
    sys_tmp = os.environ.get("TMPDIR")
    cochem_scratch = os.environ.get("COCHEM_SCRATCH_DIR")

    if slurm_tmp:
        base_dir = Path(slurm_tmp)
    elif sys_tmp:
        base_dir = Path(sys_tmp)
    elif cochem_scratch:
        base_dir = Path(cochem_scratch)
    else:
        base_dir = Path.home() / ".cochem" / "scratch"

    scratch_path = base_dir / "cochem_torq_scratch"
    scratch_path.mkdir(parents=True, exist_ok=True)
    return scratch_path
