"""CoChem-TORQ CFOUR Execution Bridge and Ephemeral Scratch Isolation Module.

Compliant with Method Matrix v4 §9, §13-§14, and Anti-Spoofing Directives.
Implements the standard ElectronicStructureExecutor interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple, Union

try:
    from Libraries.cochem_torq_cfour_bridge import (
        CFOURDipoleMoment,
        CFOUROutputPayload,
        CFOURZmatBuilder,
        TorqCfourExecutor,
    )
except ImportError:
    from cochem_torq_cfour_bridge import (
        CFOURDipoleMoment,
        CFOUROutputPayload,
        CFOURZmatBuilder,
        TorqCfourExecutor,
    )

__all__ = [
    "TorqCfourExecutor",
    "CFOURZmatBuilder",
    "CFOUROutputPayload",
    "CFOURDipoleMoment",
]
