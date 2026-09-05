"""CoChem-TORQ CREST Runner Module.

Authoritative wrapper around CREST conformer sampling tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence, Union

try:
    from Libraries.cochem_torq_crest import (
        CrestConfig,
        CrestError,
        CrestExecutionError,
        CrestRunner,
        CregenConfig,
        EnsembleContainer,
        parse_xyz_file,
        parse_xyz_string,
        write_xyz_file,
        write_xyz_string,
    )
except ImportError:
    from cochem_torq_crest import (
        CrestConfig,
        CrestError,
        CrestExecutionError,
        CrestRunner,
        CregenConfig,
        EnsembleContainer,
        parse_xyz_file,
        parse_xyz_string,
        write_xyz_file,
        write_xyz_string,
    )

__all__ = [
    "CrestConfig",
    "CrestError",
    "CrestExecutionError",
    "CrestRunner",
    "CregenConfig",
    "EnsembleContainer",
    "parse_xyz_file",
    "parse_xyz_string",
    "write_xyz_file",
    "write_xyz_string",
]
