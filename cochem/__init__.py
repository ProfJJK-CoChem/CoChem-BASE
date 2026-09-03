"""CoChem Root Package."""

from __future__ import annotations

import sys
from pathlib import Path

_src_cochem = Path(__file__).resolve().parent / "src" / "cochem"
if _src_cochem.exists() and str(_src_cochem) not in __path__:
    __path__.append(str(_src_cochem))
